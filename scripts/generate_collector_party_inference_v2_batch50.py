from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any

from app.config import get_settings
from app.services.data_go_candidate import DataGoCandidateConfig, DataGoCandidateService
from src.pipeline.contracts import new_review_queue_item
from src.pipeline.standards import COMMON_CODE_REGIONS

INPUT_ARTICLE_BATCH = "data/collector_enrichment_v2_batch.json"
INPUT_V1_EVAL = "data/collector_party_inference_v1_eval.json"
OUT_BATCH = "data/collector_party_inference_v2_batch50.json"
OUT_EVAL = "data/collector_party_inference_v2_eval.json"

PARTY_ALIASES: dict[str, tuple[str, ...]] = {
    "더불어민주당": ("더불어민주당", "민주당", "더민주", "민주"),
    "국민의힘": ("국민의힘", "국힘"),
    "조국혁신당": ("조국혁신당",),
    "개혁신당": ("개혁신당",),
    "진보당": ("진보당",),
    "정의당": ("정의당",),
    "기본소득당": ("기본소득당",),
    "무소속": ("무소속",),
}

PARTY_ALIAS_TO_CANONICAL: dict[str, str] = {
    alias: canonical for canonical, aliases in PARTY_ALIASES.items() for alias in aliases
}

CANDIDATE_NOISE_TOKENS = {
    "가상대결",
    "적합도",
    "지지율",
    "양자대결",
    "다자대결",
    "단일화",
    "정당",
    "후보",
    "시장",
    "도지사",
    "교육감",
    "구청장",
    "군수",
    "지선",
    "여론조사",
}

OFFICE_TYPE_TO_SG_TYPECODES: dict[str, tuple[str, ...]] = {
    "기초자치단체장": ("4", "3", "5"),
    "광역자치단체장": ("3", "4"),
    "교육감": ("8", "7", "3"),
}
DEFAULT_SG_TYPECODES: tuple[str, ...] = ("4", "3", "5", "6", "2")


@dataclass
class InferenceResult:
    party_inferred: str | None
    party_inference_source: str | None
    party_inference_confidence: float
    evidence: list[str]
    support_count: int = 0
    support_total: int = 0
    confidence_tier: str = "none"
    blocked_reason: str | None = None


def _clean(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _normalize_name(value: str | None) -> str | None:
    if not value:
        return None
    norm = value
    norm = norm.replace("(주)", "")
    norm = norm.replace("주식회사", "")
    norm = re.sub(r"\s+", "", norm)
    norm = re.sub(r"[^0-9a-zA-Z가-힣]", "", norm)
    norm = norm.lower()
    return norm or None


def _canonical_party(value: str | None) -> str | None:
    if not value:
        return None
    text = _clean(value)
    for alias, canonical in PARTY_ALIAS_TO_CANONICAL.items():
        if alias in text:
            return canonical
    return None


def _is_candidate_name_like(name: str | None) -> bool:
    if not name:
        return False
    text = _clean(name)
    if len(text) < 2 or len(text) > 8:
        return False
    if _canonical_party(text):
        return False
    if any(tok in text for tok in CANDIDATE_NOISE_TOKENS):
        return False
    return re.search(r"^[가-힣]{2,8}$", text) is not None


def _region_names_from_code(region_code: str | None) -> tuple[str | None, str | None]:
    if not region_code or region_code not in COMMON_CODE_REGIONS:
        return None, None
    meta = COMMON_CODE_REGIONS[region_code]
    sd_name = meta.sido_name
    sgg_name = None if meta.admin_level == "sido" else meta.sigungu_name
    return sd_name, sgg_name


def _extract_party_mentions(text: str, candidate_name: str) -> list[tuple[str, float, str]]:
    out: list[tuple[str, float, str]] = []
    cname = re.escape(candidate_name)

    alias_group = "|".join(sorted((re.escape(k) for k in PARTY_ALIAS_TO_CANONICAL.keys()), key=len, reverse=True))

    patterns: list[tuple[str, float, str]] = [
        (rf"({alias_group})\s*(?:소속|후보|예비후보)?\s*{cname}", 0.8, "party_before_candidate"),
        (rf"({alias_group})\s*{cname}", 0.72, "party_adjacent_candidate"),
        (rf"{cname}\s*\(([^\)]+)\)", 0.75, "candidate_parenthesis_party"),
        (rf"{cname}\s*(?:은|는|이|가)?\s*({alias_group})\s*(?:소속|후보|출신)?", 0.78, "candidate_before_party"),
        (rf"{cname}.{{0,8}}(무소속)", 0.82, "candidate_muso"),
        (rf"(무소속).{{0,8}}{cname}", 0.82, "muso_candidate"),
    ]

    for pattern, conf, label in patterns:
        for m in re.finditer(pattern, text):
            raw = m.group(1)
            party = _canonical_party(raw)
            if party:
                out.append((party, conf, f"{label}:{_clean(m.group(0))[:90]}"))

    return out


def _extract_gold_party_strict(text: str, candidate_name: str) -> str | None:
    cname = re.escape(candidate_name)
    alias_group = "|".join(sorted((re.escape(k) for k in PARTY_ALIAS_TO_CANONICAL.keys()), key=len, reverse=True))

    strict_patterns = [
        rf"({alias_group})\s*(?:소속|후보|예비후보)\s*{cname}",
        rf"({alias_group})\s*{cname}",
        rf"{cname}\s*\((?:[^\)]*?)({alias_group})(?:[^\)]*?)\)",
        rf"{cname}\s*(?:은|는|이|가)?\s*({alias_group})\s*(?:소속|후보|출신)",
    ]
    for pattern in strict_patterns:
        m = re.search(pattern, text)
        if not m:
            continue
        return _canonical_party(m.group(1))
    return None


def _choose_party_from_rows(rows: list[dict[str, Any]]) -> tuple[str | None, int, int, float]:
    if not rows:
        return None, 0, 0, 0.0
    counter: Counter[str] = Counter()
    for row in rows:
        party = _canonical_party(row.get("jdName"))
        if party:
            counter[party] += 1
    if not counter:
        return None, 0, 0, 0.0
    party, count = counter.most_common(1)[0]
    total = sum(counter.values())
    ratio = count / total if total else 0.0
    if len(counter) == 1:
        return party, count, total, ratio
    if ratio >= 0.65 and count >= 2:
        return party, count, total, ratio
    return None, count, total, ratio


def _confidence_tier(value: float) -> str:
    if value >= 0.85:
        return "high"
    if value >= 0.75:
        return "mid"
    if value > 0:
        return "low"
    return "none"


def _office_type_sg_types(office_type: str | None) -> tuple[str, ...]:
    return OFFICE_TYPE_TO_SG_TYPECODES.get(office_type or "", DEFAULT_SG_TYPECODES)


def _endpoint_with_page(endpoint_url: str, page_no: int) -> str:
    sep = "&" if "?" in endpoint_url else "?"
    return f"{endpoint_url}{sep}pageNo={page_no}"


class DataGoRegistryProvider:
    def __init__(
        self,
        *,
        sg_id: str,
        enabled: bool,
        max_pages: int = 8,
        page_size: int = 100,
    ):
        self.sg_id = sg_id
        self.enabled = enabled
        self.max_pages = max_pages
        self.page_size = page_size
        self._cache: dict[tuple[str, str | None, str | None], list[dict[str, Any]]] = {}

        self._endpoint = ""
        self._service_key: str | None = None
        if enabled:
            try:
                settings = get_settings()
                self._endpoint = settings.data_go_candidate_endpoint_url
                self._service_key = settings.data_go_kr_key
            except Exception:
                self.enabled = False

    def _fetch_one_page(
        self,
        *,
        sg_typecode: str,
        page_no: int,
        sd_name: str | None,
        sgg_name: str | None,
    ) -> list[dict[str, Any]]:
        endpoint_url = _endpoint_with_page(self._endpoint, page_no)
        cfg = DataGoCandidateConfig(
            endpoint_url=endpoint_url,
            service_key=self._service_key,
            sg_id=self.sg_id,
            sg_typecode=sg_typecode,
            sd_name=sd_name,
            sgg_name=sgg_name,
            timeout_sec=4.0,
            max_retries=1,
            cache_ttl_sec=120,
            requests_per_sec=8.0,
            num_of_rows=self.page_size,
        )
        service = DataGoCandidateService(cfg)
        return service.fetch_items()

    def fetch(self, *, sg_typecode: str, sd_name: str | None, sgg_name: str | None) -> list[dict[str, Any]]:
        key = (sg_typecode, sd_name, sgg_name)
        if key in self._cache:
            return self._cache[key]
        if not self.enabled or not self._endpoint or not self._service_key:
            self._cache[key] = []
            return []

        all_rows: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str, str]] = set()

        for page_no in range(1, self.max_pages + 1):
            try:
                rows = self._fetch_one_page(
                    sg_typecode=sg_typecode,
                    page_no=page_no,
                    sd_name=sd_name,
                    sgg_name=sgg_name,
                )
            except Exception:
                rows = []

            if not rows:
                break

            for row in rows:
                k = (
                    str(row.get("name") or ""),
                    str(row.get("jdName") or ""),
                    str(row.get("sdName") or ""),
                    str(row.get("sggName") or ""),
                )
                if k in seen:
                    continue
                seen.add(k)
                all_rows.append({**row, "_sg_typecode": sg_typecode})

            if len(rows) < self.page_size:
                break

        self._cache[key] = all_rows
        return all_rows

    def find_matches(
        self,
        *,
        candidate_name: str,
        sd_name: str | None,
        sgg_name: str | None,
        office_type: str | None,
        include_sd_fallback: bool,
        include_global: bool,
    ) -> list[dict[str, Any]]:
        target = _normalize_name(candidate_name)
        if not target:
            return []

        scopes: list[tuple[str | None, str | None]] = [(sd_name, sgg_name)]
        if include_sd_fallback and sd_name:
            scopes.append((sd_name, None))
        if include_global:
            scopes.append((None, None))

        rows: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str, str, str]] = set()
        for sg_typecode in _office_type_sg_types(office_type):
            for sd_q, sgg_q in scopes:
                for row in self.fetch(sg_typecode=sg_typecode, sd_name=sd_q, sgg_name=sgg_q):
                    if _normalize_name(row.get("name")) != target:
                        continue
                    k = (
                        str(row.get("name") or ""),
                        str(row.get("jdName") or ""),
                        str(row.get("sdName") or ""),
                        str(row.get("sggName") or ""),
                        str(row.get("_sg_typecode") or ""),
                    )
                    if k in seen:
                        continue
                    seen.add(k)
                    rows.append(row)
        return rows


def _build_latest_registry_from_context(records: list[dict[str, Any]]) -> dict[str, Counter[str]]:
    by_name: dict[str, Counter[str]] = defaultdict(Counter)
    for row in records:
        article = row.get("article") or {}
        text = _clean(f"{article.get('title') or ''} {article.get('raw_text') or ''}")
        for cand in (row.get("candidates") or []):
            name = _clean(cand.get("name_ko"))
            name_norm = _normalize_name(name)
            if not name_norm or not _is_candidate_name_like(name):
                continue
            mentions = _extract_party_mentions(text, name)
            for party, conf, _evidence in mentions:
                if conf >= 0.75:
                    by_name[name_norm][party] += 1
    return by_name


def infer_party_for_candidate(
    *,
    candidate_name: str,
    article_text: str,
    region_code: str | None,
    office_type: str | None,
    provider: DataGoRegistryProvider,
    latest_registry: dict[str, Counter[str]] | None = None,
) -> InferenceResult:
    if not _is_candidate_name_like(candidate_name):
        return InferenceResult(
            party_inferred=None,
            party_inference_source=None,
            party_inference_confidence=0.0,
            evidence=[],
            blocked_reason="candidate_name_noise_or_invalid",
        )

    evidence: list[str] = []
    sd_name, sgg_name = _region_names_from_code(region_code)

    # 1) Data.go.kr 지역 범위 조회 (office_type -> sg_typecodes)
    region_rows = provider.find_matches(
        candidate_name=candidate_name,
        sd_name=sd_name,
        sgg_name=sgg_name,
        office_type=office_type,
        include_sd_fallback=False,
        include_global=False,
    )
    party, count, total, ratio = _choose_party_from_rows(region_rows)
    if party:
        conf = 0.96 if ratio >= 0.99 and total >= 2 else (0.9 if ratio >= 0.75 else 0.84)
        evidence.append(
            f"data_go_region rows={len(region_rows)} count={count}/{total} ratio={round(ratio,3)} sd={sd_name} sgg={sgg_name}"
        )
        return InferenceResult(
            party_inferred=party,
            party_inference_source="data_go_candidate_api_region",
            party_inference_confidence=conf,
            confidence_tier=_confidence_tier(conf),
            evidence=evidence,
            support_count=count,
            support_total=total,
        )

    # 2) 시도/전국 fallback 포함한 최신 후보 등록정보 집계
    merged_rows = provider.find_matches(
        candidate_name=candidate_name,
        sd_name=sd_name,
        sgg_name=sgg_name,
        office_type=office_type,
        include_sd_fallback=True,
        include_global=True,
    )
    party2, count2, total2, ratio2 = _choose_party_from_rows(merged_rows)
    if party2:
        conf = 0.88 if ratio2 >= 0.9 else (0.82 if ratio2 >= 0.75 else 0.76)
        evidence.append(f"latest_registry_v2 rows={len(merged_rows)} count={count2}/{total2} ratio={round(ratio2,3)}")
        return InferenceResult(
            party_inferred=party2,
            party_inference_source="latest_candidate_registry_v2",
            party_inference_confidence=conf,
            confidence_tier=_confidence_tier(conf),
            evidence=evidence,
            support_count=count2,
            support_total=total2,
        )

    # 3) 기사 내부 문맥 기반 레지스트리 백업
    name_norm = _normalize_name(candidate_name)
    context_counter = (latest_registry or {}).get(name_norm or "", Counter())
    if context_counter:
        top_party, top_count = context_counter.most_common(1)[0]
        total_ctx = sum(context_counter.values())
        ratio_ctx = top_count / total_ctx if total_ctx else 0.0
        if ratio_ctx >= 0.75 and top_count >= 2:
            conf = 0.8 if ratio_ctx >= 0.9 else 0.75
            evidence.append(f"context_registry count={top_count}/{total_ctx} ratio={round(ratio_ctx,3)}")
            return InferenceResult(
                party_inferred=top_party,
                party_inference_source="context_registry_v2",
                party_inference_confidence=conf,
                confidence_tier=_confidence_tier(conf),
                evidence=evidence,
                support_count=top_count,
                support_total=total_ctx,
            )

    # 4) 기사 문맥 단서
    mentions = _extract_party_mentions(article_text, candidate_name)
    if mentions:
        party_counter: Counter[str] = Counter(p for p, _c, _e in mentions)
        top_party, top_count = party_counter.most_common(1)[0]
        total_mentions = sum(party_counter.values())
        ratio_m = top_count / total_mentions if total_mentions else 0.0
        top_conf = max(conf for p, conf, _e in mentions if p == top_party)
        ev = [ev for p, _conf, ev in mentions if p == top_party][:2]

        if len(party_counter) == 1:
            conf = max(top_conf, 0.75)
            return InferenceResult(
                party_inferred=top_party,
                party_inference_source="article_context",
                party_inference_confidence=conf,
                confidence_tier=_confidence_tier(conf),
                evidence=ev,
                support_count=top_count,
                support_total=total_mentions,
            )

        if ratio_m >= 0.75 and top_count >= 2:
            conf = max(0.75, min(0.79, top_conf - 0.02))
            return InferenceResult(
                party_inferred=top_party,
                party_inference_source="article_context_dominant",
                party_inference_confidence=conf,
                confidence_tier=_confidence_tier(conf),
                evidence=ev,
                support_count=top_count,
                support_total=total_mentions,
            )

        return InferenceResult(
            party_inferred=None,
            party_inference_source=None,
            party_inference_confidence=0.0,
            evidence=ev,
            support_count=top_count,
            support_total=total_mentions,
            blocked_reason="conflicting_party_signals",
        )

    return InferenceResult(
        party_inferred=None,
        party_inference_source=None,
        party_inference_confidence=0.0,
        evidence=evidence,
        blocked_reason="no_reliable_party_signal",
    )


def generate_party_inference_v2(*, input_path: str = INPUT_ARTICLE_BATCH, sample_size: int = 50) -> dict[str, Any]:
    payload = json.loads(Path(input_path).read_text(encoding="utf-8"))
    records = (payload.get("records") or [])[:sample_size]

    provider = DataGoRegistryProvider(sg_id="20260603", enabled=True)
    latest_registry = _build_latest_registry_from_context(records)

    review_queue: list[dict[str, Any]] = []
    source_counter: Counter[str] = Counter()
    confidence_buckets: Counter[str] = Counter()
    blocked_reason_counter: Counter[str] = Counter()
    error_counter: Counter[str] = Counter()

    target_candidates = 0
    inferred_candidates = 0
    high_conf_candidates = 0

    gold_total = 0
    gold_tp = 0
    gold_fp = 0
    gold_fn = 0

    support_sum = 0
    support_total_sum = 0

    mismatch_samples: list[dict[str, Any]] = []
    inferred_samples: list[dict[str, Any]] = []

    out_records: list[dict[str, Any]] = []

    for ridx, row in enumerate(records):
        article = row.get("article") or {}
        obs = row.get("observation") or {}
        text = _clean(f"{article.get('title') or ''} {article.get('raw_text') or ''}")
        region_code = obs.get("region_code")
        office_type = obs.get("office_type")

        new_row = dict(row)
        new_candidates: list[dict[str, Any]] = []

        for cidx, cand in enumerate(row.get("candidates") or []):
            new_cand = dict(cand)
            name = _clean(cand.get("name_ko"))
            existing_party = _canonical_party(cand.get("party_name"))

            if existing_party:
                new_cand["party_inferred"] = existing_party
                new_cand["party_inference_source"] = "already_present"
                new_cand["party_inference_confidence"] = 1.0
                new_cand["party_inference_confidence_tier"] = "high"
                new_cand["party_inference_support_count"] = 1
                new_cand["party_inference_support_total"] = 1
                new_candidates.append(new_cand)
                continue

            target_candidates += 1

            result = infer_party_for_candidate(
                candidate_name=name,
                article_text=text,
                region_code=region_code,
                office_type=office_type,
                provider=provider,
                latest_registry=latest_registry,
            )

            new_cand["party_inferred"] = result.party_inferred
            new_cand["party_inference_source"] = result.party_inference_source
            new_cand["party_inference_confidence"] = round(float(result.party_inference_confidence), 4)
            new_cand["party_inference_confidence_tier"] = result.confidence_tier
            new_cand["party_inference_support_count"] = result.support_count
            new_cand["party_inference_support_total"] = result.support_total

            if result.evidence:
                new_cand["party_inference_evidence"] = result.evidence[:3]

            confidence_buckets[result.confidence_tier] += 1
            if result.blocked_reason:
                blocked_reason_counter[result.blocked_reason] += 1

            if result.party_inferred:
                inferred_candidates += 1
                support_sum += result.support_count
                support_total_sum += result.support_total
                source_counter[result.party_inference_source or "unknown"] += 1
                inferred_samples.append(
                    {
                        "article_url": article.get("url"),
                        "article_title": article.get("title"),
                        "candidate_name": name,
                        "pred_party": result.party_inferred,
                        "inference_source": result.party_inference_source,
                        "confidence": round(float(result.party_inference_confidence), 4),
                        "support": f"{result.support_count}/{result.support_total}",
                        "evidence": result.evidence[:2],
                    }
                )
                if result.party_inference_confidence >= 0.8:
                    high_conf_candidates += 1
                    new_cand["party_name"] = result.party_inferred

            gold_party = _extract_gold_party_strict(text, name)
            if gold_party:
                gold_total += 1
                if result.party_inferred == gold_party:
                    gold_tp += 1
                elif result.party_inferred is None:
                    gold_fn += 1
                else:
                    gold_fp += 1
                    gold_fn += 1
                    if len(mismatch_samples) < 5:
                        mismatch_samples.append(
                            {
                                "article_url": article.get("url"),
                                "article_title": article.get("title"),
                                "candidate_name": name,
                                "gold_party": gold_party,
                                "pred_party": result.party_inferred,
                                "inference_source": result.party_inference_source,
                                "confidence": round(float(result.party_inference_confidence), 4),
                                "evidence": result.evidence[:2],
                            }
                        )

            low_conf = (result.party_inferred is None) or (result.party_inference_confidence < 0.75)
            if low_conf:
                if result.party_inferred is None:
                    if result.blocked_reason == "conflicting_party_signals":
                        error_code = "PARTY_INFERENCE_CONFLICT_SIGNALS"
                        error_message = "party inference has conflicting party signals"
                    elif result.blocked_reason == "candidate_name_noise_or_invalid":
                        error_code = "PARTY_INFERENCE_INVALID_CANDIDATE"
                        error_message = "candidate name invalid for party inference"
                    else:
                        error_code = "PARTY_INFERENCE_NO_SIGNAL"
                        error_message = "party inference unresolved"
                else:
                    error_code = "PARTY_INFERENCE_LOW_CONFIDENCE"
                    error_message = "party inference confidence below threshold"

                error_counter[error_code] += 1
                review_queue.append(
                    new_review_queue_item(
                        entity_type="poll_option",
                        entity_id=f"{obs.get('observation_key') or f'obs-{ridx}'}:{cidx}",
                        issue_type="mapping_error",
                        stage="infer_party",
                        error_code=error_code,
                        error_message=error_message,
                        source_url=article.get("url"),
                        payload={
                            "candidate_name": name,
                            "party_inferred": result.party_inferred,
                            "party_inference_source": result.party_inference_source,
                            "party_inference_confidence": round(float(result.party_inference_confidence), 4),
                            "party_inference_confidence_tier": result.confidence_tier,
                            "support_count": result.support_count,
                            "support_total": result.support_total,
                            "blocked_reason": result.blocked_reason,
                            "evidence": result.evidence[:3],
                        },
                    ).to_dict()
                )

            new_candidates.append(new_cand)

        new_row["candidates"] = new_candidates
        out_records.append(new_row)

    precision = gold_tp / (gold_tp + gold_fp) if (gold_tp + gold_fp) else 0.0
    recall = gold_tp / (gold_tp + gold_fn) if (gold_tp + gold_fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    wrong_top5 = mismatch_samples[:5]
    if not wrong_top5 and inferred_samples:
        inferred_samples_sorted = sorted(inferred_samples, key=lambda x: x["confidence"])
        wrong_top5 = []
        for row in inferred_samples_sorted[:5]:
            wrong_top5.append({**row, "gold_party": None, "inspection_result": "manual_review_required_no_gold"})

    v1_eval = {}
    if Path(INPUT_V1_EVAL).exists():
        v1_eval = json.loads(Path(INPUT_V1_EVAL).read_text(encoding="utf-8"))

    v1_inferred = int(v1_eval.get("candidate_inferred_count", 0)) if isinstance(v1_eval, dict) else 0
    v1_high_conf = int(v1_eval.get("candidate_high_conf_count", 0)) if isinstance(v1_eval, dict) else 0

    eval_payload = {
        "sample_size_articles": len(out_records),
        "candidate_target_count": target_candidates,
        "candidate_inferred_count": inferred_candidates,
        "candidate_high_conf_count": high_conf_candidates,
        "inference_coverage": round(inferred_candidates / target_candidates, 4) if target_candidates else 0.0,
        "source_distribution": dict(source_counter),
        "confidence_distribution": dict(confidence_buckets),
        "blocked_reason_distribution": dict(blocked_reason_counter),
        "support_stats": {
            "avg_support_count": round(support_sum / inferred_candidates, 4) if inferred_candidates else 0.0,
            "avg_support_total": round(support_total_sum / inferred_candidates, 4) if inferred_candidates else 0.0,
        },
        "v1_comparison": {
            "candidate_inferred_count_v1": v1_inferred,
            "candidate_inferred_delta": inferred_candidates - v1_inferred,
            "candidate_high_conf_count_v1": v1_high_conf,
            "candidate_high_conf_delta": high_conf_candidates - v1_high_conf,
        },
        "evaluation_gold_labeled_count": gold_total,
        "evaluation_metrics": {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "tp": gold_tp,
            "fp": gold_fp,
            "fn": gold_fn,
        },
        "wrong_inference_top5": wrong_top5,
        "blocking_rules": [
            "1) 후보명이 정당/직함/지표 토큰이면 추정 차단",
            "2) confidence < 0.75 또는 무신호는 review_queue 라우팅",
            "3) Data.go는 office_type별 sg_typecode 후보군 + pagination(pageNo) 조회",
            "4) 다중 정당 신호는 ratio>=0.75 우세가 없으면 auto infer 금지",
            "5) 근거 수(support_count/total)와 confidence_tier를 함께 저장",
        ],
        "review_queue_count": len(review_queue),
        "failure_types_top5": [{"type": k, "count": v} for k, v in error_counter.most_common(5)],
    }

    batch_payload = {
        "run_type": "collector_party_inference_v2",
        "extractor_version": "party-inference-v2",
        "source_payload": input_path,
        "records": out_records,
        "review_queue_candidates": review_queue,
    }

    return {"batch": batch_payload, "eval": eval_payload}


def main() -> None:
    out = generate_party_inference_v2()
    Path(OUT_BATCH).write_text(json.dumps(out["batch"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    Path(OUT_EVAL).write_text(json.dumps(out["eval"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(out["eval"], ensure_ascii=False, indent=2))
    print("written:", OUT_BATCH)
    print("written:", OUT_EVAL)


if __name__ == "__main__":
    main()
