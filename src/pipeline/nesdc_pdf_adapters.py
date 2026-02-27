from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import re
from typing import Any

from .contracts import normalize_value

TOP10_POLLSTERS: tuple[str, ...] = (
    "(주)엠브레인퍼블릭",
    "(주)리얼미터",
    "케이스탯리서치",
    "(주)코리아정보리서치",
    "한국갤럽조사연구소",
    "케이에스오아이 주식회사(한국사회여론연구소)",
    "입소스 주식회사",
    "(주)한국리서치",
    "(주)비전코리아",
    "한길리서치",
)


@dataclass(frozen=True)
class AdapterResolution:
    result_items: list[dict[str, Any]]
    adapter_mode: str
    adapter_profile: dict[str, Any]
    fallback_applied: bool
    parser_name: str | None = None
    matched_adapter_ntt_id: str | None = None


class NesdcPdfAdapterEngine:
    _NAME_VALUE_RE = re.compile(r"([가-힣A-Za-z0-9·()]{2,30})\s*[:：]?\s*(\d{1,3}(?:\.\d+)?)\s*%")
    _NOISE_OPTION_TOKENS = {
        "신뢰수준",
        "응답률",
        "표본",
        "표본오차",
        "오차범위",
        "조사대상",
        "조사일시",
        "조사방법",
        "사례수",
        "무응답",
        "없음",
    }
    _OCR_KEYS = ("pdf_ocr_text", "ocr_text", "extracted_text_ocr")
    _RULE_KEYS = ("result_text", "pdf_text", "summary_text", "raw_text", "body_text")

    def __init__(self, adapter_rows: list[dict[str, Any]] | None = None) -> None:
        rows = list(adapter_rows or [])
        self._adapter_by_ntt: dict[str, dict[str, Any]] = {
            str(r.get("ntt_id")): r for r in rows if r.get("ntt_id") is not None
        }
        self._template_by_pollster: dict[str, dict[str, Any]] = {}
        for row in rows:
            pollster = str(row.get("pollster") or "").strip()
            if not pollster or pollster in self._template_by_pollster:
                continue
            if row.get("result_items"):
                self._template_by_pollster[pollster] = row

    def resolve(self, registry_row: dict[str, Any]) -> AdapterResolution:
        ntt_id = str(registry_row.get("ntt_id") or "")
        pollster = str(registry_row.get("pollster") or "미상조사기관")

        exact = self._adapter_by_ntt.get(ntt_id)
        if exact and (exact.get("result_items") or []):
            return AdapterResolution(
                result_items=self._normalize_items(exact.get("result_items") or []),
                adapter_mode="adapter_exact",
                adapter_profile={"profile_key": f"ntt:{ntt_id}", "pollster": pollster},
                fallback_applied=False,
                parser_name="pollster_template_exact",
                matched_adapter_ntt_id=ntt_id,
            )

        template = self._template_by_pollster.get(pollster)
        if template and (template.get("result_items") or []):
            return AdapterResolution(
                result_items=self._normalize_items(template.get("result_items") or []),
                adapter_mode="adapter_pollster_template_fallback",
                adapter_profile={"profile_key": f"pollster:{pollster}", "pollster": pollster},
                fallback_applied=True,
                parser_name="pollster_template_fallback",
                matched_adapter_ntt_id=str(template.get("ntt_id") or "") or None,
            )

        ocr_text = self._collect_text(registry_row, keys=self._OCR_KEYS)
        if ocr_text:
            ocr_items = self._parse_name_values(ocr_text, question="OCR 결과")
            if ocr_items:
                return AdapterResolution(
                    result_items=ocr_items,
                    adapter_mode="adapter_ocr_fallback",
                    adapter_profile={"profile_key": f"fallback:ocr:{pollster}", "pollster": pollster},
                    fallback_applied=True,
                    parser_name="ocr_regex_v1",
                    matched_adapter_ntt_id=None,
                )

        rule_text = self._collect_text(registry_row, keys=self._RULE_KEYS)
        if rule_text:
            rule_items = self._parse_name_values(rule_text, question="규칙 파서 결과")
            if rule_items:
                return AdapterResolution(
                    result_items=rule_items,
                    adapter_mode="adapter_rule_fallback",
                    adapter_profile={"profile_key": f"fallback:rule:{pollster}", "pollster": pollster},
                    fallback_applied=True,
                    parser_name="rule_regex_v1",
                    matched_adapter_ntt_id=None,
                )

        return AdapterResolution(
            result_items=[],
            adapter_mode="fallback",
            adapter_profile={"profile_key": f"fallback:none:{pollster}", "pollster": pollster},
            fallback_applied=True,
            parser_name=None,
            matched_adapter_ntt_id=None,
        )

    def _normalize_items(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for row in rows:
            value_raw = row.get("value_raw")
            norm = normalize_value(value_raw)
            out.append(
                {
                    "question": row.get("question"),
                    "option": row.get("option"),
                    "value_raw": value_raw,
                    "value_min": norm.value_min,
                    "value_max": norm.value_max,
                    "value_mid": norm.value_mid,
                    "is_missing": norm.is_missing,
                    "provenance": row.get("provenance") or {},
                }
            )
        return out

    @classmethod
    def _collect_text(cls, row: dict[str, Any], *, keys: tuple[str, ...]) -> str:
        chunks: list[str] = []
        for key in keys:
            val = row.get(key)
            if isinstance(val, str) and val.strip():
                chunks.append(val.strip())
        return "\n".join(chunks)

    @classmethod
    def _parse_name_values(cls, text: str, *, question: str) -> list[dict[str, Any]]:
        seen: set[str] = set()
        items: list[dict[str, Any]] = []

        for idx, (name, value) in enumerate(cls._NAME_VALUE_RE.findall(text), start=1):
            option = re.sub(r"\s+", "", name.strip())
            if not option:
                continue
            if any(token in option for token in cls._NOISE_OPTION_TOKENS):
                continue
            if option in seen:
                continue
            seen.add(option)

            value_raw = f"{value}%"
            norm = normalize_value(value_raw)
            items.append(
                {
                    "question": question,
                    "option": option,
                    "value_raw": value_raw,
                    "value_min": norm.value_min,
                    "value_max": norm.value_max,
                    "value_mid": norm.value_mid,
                    "is_missing": norm.is_missing,
                    "provenance": {
                        "source_channel": "nesdc",
                        "paragraph": idx,
                        "parser": "regex",
                    },
                }
            )
            if len(items) >= 8:
                break

        return items


def build_top10_pollster_template_profile(
    *,
    registry_rows: list[dict[str, Any]],
    adapter_rows: list[dict[str, Any]],
    top_n: int = 10,
) -> dict[str, Any]:
    pollster_counter: Counter[str] = Counter(
        str(row.get("pollster") or "").strip() for row in registry_rows if str(row.get("pollster") or "").strip()
    )
    top_pollsters = [name for name, _ in pollster_counter.most_common(top_n)]

    adapter_by_pollster: dict[str, list[dict[str, Any]]] = {}
    for row in adapter_rows:
        pollster = str(row.get("pollster") or "").strip()
        if not pollster:
            continue
        adapter_by_pollster.setdefault(pollster, []).append(row)

    profiles: list[dict[str, Any]] = []
    covered = 0
    for pollster in top_pollsters:
        rows = adapter_by_pollster.get(pollster) or []
        rows_with_items = [r for r in rows if r.get("result_items")]
        has_template = bool(rows_with_items)
        if has_template:
            covered += 1
        profiles.append(
            {
                "pollster": pollster,
                "registry_count": pollster_counter.get(pollster, 0),
                "adapter_record_count": len(rows),
                "adapter_result_item_ready_count": len(rows_with_items),
                "template_ntt_ids": [str(r.get("ntt_id") or "") for r in rows_with_items[:5]],
                "adapter_strategy": "pollster_template" if has_template else "fallback_ocr_rule",
            }
        )

    return {
        "top_n": top_n,
        "top_pollsters": profiles,
        "covered_pollster_count": covered,
        "coverage_ratio": round(covered / max(1, len(top_pollsters)), 4),
        "recommended_seed_pollsters": [
            row["pollster"] for row in profiles if row["adapter_strategy"] == "fallback_ocr_rule"
        ],
        "target_reference": list(TOP10_POLLSTERS),
    }
