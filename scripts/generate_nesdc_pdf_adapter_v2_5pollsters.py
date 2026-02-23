from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from html import unescape
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

BASE_URL = "https://www.nesdc.go.kr"
LIST_BASE = f"{BASE_URL}/portal/bbs/B0000005/list.do?menuNo=200467"
USER_AGENT = "ElectionCollector/0.1 NESDC-AdapterPilot-v1"
TARGET_POLLSTERS = (
    "(주)엠브레인퍼블릭",
    "케이스탯리서치",
    "(주)코리아리서치인터내셔널",
    "(주)리얼미터",
    "KOPRA",
)
OUTPUT_DATA = "data/nesdc_pdf_adapter_v2_5pollsters.json"
OUTPUT_EVAL = "data/nesdc_pdf_adapter_v2_5pollsters_eval.json"
MIN_PER_POLLSTER = 1


@dataclass
class EvalCounter:
    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0

    def to_metrics(self) -> dict[str, float]:
        precision = self.tp / (self.tp + self.fp) if (self.tp + self.fp) else 0.0
        recall = self.tp / (self.tp + self.fn) if (self.tp + self.fn) else 0.0
        accuracy = (self.tp + self.tn) / (self.tp + self.tn + self.fp + self.fn) if (self.tp + self.tn + self.fp + self.fn) else 0.0
        return {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "accuracy": round(accuracy, 4),
            "tp": self.tp,
            "fp": self.fp,
            "fn": self.fn,
            "tn": self.tn,
        }


def _http_get_text(url: str, timeout: int = 20) -> str:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        charset = resp.headers.get_content_charset() or "utf-8"
        return raw.decode(charset, errors="replace")


def _clean(text: str | None) -> str:
    if not text:
        return ""
    s = re.sub(r"<br\s*/?>", " ", text, flags=re.IGNORECASE)
    s = re.sub(r"<[^>]+>", " ", s)
    s = unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def _parse_list_page(html: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    pattern = re.compile(
        r"<a\s+href=\"(/portal/bbs/B0000005/view\.do\?[^\"]+)\"\s+class=\"row tr\">(.*?)</a>",
        flags=re.IGNORECASE | re.DOTALL,
    )
    for href, body in pattern.findall(html):
        cols = re.findall(r"<span class=\"col[^\"]*\">\s*<i class=\"tit\"></i>(.*?)</span>", body, flags=re.IGNORECASE | re.DOTALL)
        cols = [_clean(c) for c in cols]
        if len(cols) < 8:
            continue
        ntt = re.search(r"nttId=(\d+)", href)
        if not ntt:
            continue
        rows.append(
            {
                "ntt_id": ntt.group(1),
                # 검색어 파라미터(한글) 없이 nttId 기반 canonical URL 사용
                "detail_url": f"{BASE_URL}/portal/bbs/B0000005/view.do?menuNo=200467&nttId={ntt.group(1)}",
                "registration_number": cols[0],
                "pollster": cols[1],
                "sponsor": cols[2],
                "method": cols[3],
                "sampling_frame": cols[4],
                "election_region": cols[5],
                "registered_at": cols[6],
                "sido": cols[7],
            }
        )
    return rows


def _collect_pollster_rows(pollster: str, min_count: int = 10) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    enc = quote(pollster)
    for page in range(1, 30):
        url = f"{LIST_BASE}&searchCnd=1&searchWrd={enc}&pageIndex={page}"
        html = _http_get_text(url)
        rows = _parse_list_page(html)
        if not rows:
            break
        for row in rows:
            ntt = row.get("ntt_id")
            if not ntt or ntt in seen:
                continue
            seen.add(ntt)
            out.append(row)
            if len(out) >= min_count:
                break
        if len(out) >= min_count:
            break
    return out


def _parse_rows(html: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, row_html in enumerate(re.findall(r"<tr[^>]*>(.*?)</tr>", html, flags=re.IGNORECASE | re.DOTALL), start=1):
        ths = [_clean(v) for v in re.findall(r"<th[^>]*>(.*?)</th>", row_html, flags=re.IGNORECASE | re.DOTALL)]
        tds = [_clean(v) for v in re.findall(r"<td[^>]*>(.*?)</td>", row_html, flags=re.IGNORECASE | re.DOTALL)]
        rows.append({"idx": idx, "ths": ths, "tds": tds, "html": row_html})
    return rows


def _find_first_tds(rows: list[dict[str, Any]], key: str) -> str | None:
    for r in rows:
        if key in " ".join(r["ths"]):
            if r["tds"]:
                return r["tds"][0] or None
    return None


def _extract_sample_size(html: str, rows: list[dict[str, Any]]) -> int | None:
    m = re.search(r"id=\"sampleSexSizeSum\">\s*([0-9,]+)\s*</span>", html)
    if m:
        return int(m.group(1).replace(",", ""))
    for r in rows:
        key = " ".join(r["ths"])
        if "조사완료 사례수" in key and r["tds"]:
            m2 = re.search(r"([0-9,]{2,8})", " ".join(r["tds"]))
            if m2:
                return int(m2.group(1).replace(",", ""))
    return None


def _extract_percent(value: str | None) -> float | None:
    if not value:
        return None
    m = re.search(r"(\d{1,3}(?:\.\d+)?)\s*%", value)
    if not m:
        return None
    return float(m.group(1))


def _extract_result_items(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    current_question = ""
    for r in rows:
        ths = r["ths"]
        tds = r["tds"]
        if not ths and not tds:
            continue

        if len(ths) == 1 and not tds and ths[0]:
            current_question = ths[0]
            continue

        row_text = " ".join(tds)
        m = re.search(r"(\d{1,3}(?:\.\d+)?)\s*%", row_text)
        if not m:
            continue

        option = " ".join([t for t in ths if t]).strip() or "미상선택지"
        value_raw = f"{m.group(1)}%"
        value = float(m.group(1))

        items.append(
            {
                "question": current_question or "결과블록",
                "option": option,
                "value_raw": value_raw,
                "value": value,
                "provenance": {
                    "source_channel": "nesdc",
                    "page": 1,
                    "paragraph": r["idx"],
                    "html_excerpt": _clean(r["html"])[:220],
                },
            }
        )
    return items


def _gold_result_items(rows: list[dict[str, Any]]) -> list[tuple[str, str]]:
    gold: list[tuple[str, str]] = []
    for r in rows:
        th = " ".join(r["ths"]).strip()
        td = " ".join(r["tds"])
        m = re.search(r"(\d{1,3}(?:\.\d+)?)\s*%", td)
        if not m:
            continue
        if not th:
            continue
        gold.append((th, f"{m.group(1)}%"))
    return gold


def _parse_detail(row: dict[str, Any]) -> dict[str, Any]:
    html = _http_get_text(row["detail_url"])
    rows = _parse_rows(html)

    survey_datetime = _find_first_tds(rows, "조사일시")
    survey_population = _find_first_tds(rows, "조사대상")
    response_rate = _extract_percent(_find_first_tds(rows, "전체 응답률") or _find_first_tds(rows, "응답률 (I/(I+R))"))
    margin = _find_first_tds(rows, "표본오차")
    sample_size = _extract_sample_size(html, rows)

    legal_meta = {
        "survey_datetime": survey_datetime,
        "survey_population": survey_population,
        "sample_size": sample_size,
        "response_rate": response_rate,
        "margin_of_error": margin,
        "method": row.get("method"),
    }

    result_items = _extract_result_items(rows)
    gold_items = _gold_result_items(rows)

    return {
        **row,
        "source_channel": "nesdc",
        "source_detail_url": row["detail_url"],
        "legal_meta": legal_meta,
        "result_items": result_items,
        "_gold_result_items": gold_items,
        "_html_rows": rows,
    }


def _field_presence_expected(rows: list[dict[str, Any]], key: str) -> bool:
    return any(key in " ".join(r["ths"]) for r in rows)


def _evaluate(records: list[dict[str, Any]]) -> dict[str, Any]:
    field_map = {
        "survey_datetime": "조사일시",
        "survey_population": "조사대상",
        "sample_size": "조사완료 사례수",
        "response_rate": "전체 응답률",
        "margin_of_error": "표본오차",
        "method": "조사방법",
    }

    field_counters: dict[str, EvalCounter] = {k: EvalCounter() for k in field_map}
    result_counter = EvalCounter()
    failure_counter: Counter[str] = Counter()

    for rec in records:
        rows = rec["_html_rows"]
        legal = rec["legal_meta"]

        for field, label in field_map.items():
            expected = _field_presence_expected(rows, label)
            if field == "sample_size":
                expected = expected or (re.search(r"sampleSexSizeSum", " ".join(r["html"] for r in rows)) is not None)
            predicted = legal.get(field) not in (None, "", [])

            c = field_counters[field]
            if expected and predicted:
                c.tp += 1
            elif expected and not predicted:
                c.fn += 1
                failure_counter[f"MISSING_{field.upper()}"] += 1
            elif (not expected) and predicted:
                c.fp += 1
            else:
                c.tn += 1

        pred_set = {(item["option"], item["value_raw"]) for item in rec["result_items"]}
        gold_set = set(rec["_gold_result_items"])
        if not pred_set:
            failure_counter["NO_RESULT_BLOCK"] += 1
        if len(pred_set) <= 1:
            failure_counter["LOW_RESULT_ITEM_COUNT"] += 1
        fp_items = pred_set - gold_set
        fn_items = gold_set - pred_set
        if fp_items:
            failure_counter["RESULT_OPTION_VALUE_MISMATCH_FP"] += len(fp_items)
        if fn_items:
            failure_counter["RESULT_OPTION_VALUE_MISMATCH_FN"] += len(fn_items)

        result_counter.tp += len(pred_set & gold_set)
        result_counter.fp += len(fp_items)
        result_counter.fn += len(fn_items)

    per_field_metrics = {k: v.to_metrics() for k, v in field_counters.items()}

    eval_payload = {
        "sample_size": len(records),
        "pollster_distribution": dict(Counter(r.get("pollster") for r in records)),
        "field_metrics": per_field_metrics,
        "result_block_metrics": result_counter.to_metrics(),
        "parse_success_rate": round(sum(1 for r in records if r["result_items"]) / len(records), 4) if records else 0.0,
        "failure_types_top5": [{"type": k, "count": v} for k, v in failure_counter.most_common(5)],
        "improvement_priorities": [
            "1) 결과블록 테이블 헤더-값 매칭 고도화(다단 헤더 대응)",
            "2) 조사방법은 목록값 외 상세 원문 라벨 파싱 추가",
            "3) 표본크기 대체 규칙(sampleSexSizeSum 미존재 시 표 본문 합계 계산)",
            "4) 옵션명 정규화(접촉현황/응답현황 공통 라벨 사전)",
            "5) PDF 본문 좌표(page/paragraph) 실측 모듈 연결(v2)",
        ],
    }
    return eval_payload


def generate_adapter_v2_5pollsters() -> dict[str, Any]:
    collected: list[dict[str, Any]] = []
    per_pollster_counts: dict[str, int] = {}

    for pollster in TARGET_POLLSTERS:
        base_rows = _collect_pollster_rows(pollster, min_count=max(12, MIN_PER_POLLSTER * 4))
        qualified_rows: list[dict[str, Any]] = []
        fallback_rows: list[dict[str, Any]] = []
        for row in base_rows:
            try:
                parsed = _parse_detail(row)
            except Exception:
                continue

            # pilot 대상: 결과분석 PDF 첨부 문구가 있고 최초공표 정보가 있는 케이스 우선
            html_text = " ".join(r["html"] for r in parsed["_html_rows"])
            has_pdf_section = "결과분석 자료" in html_text
            has_first_publish = "최초 공표·보도 지정일시" in html_text
            if has_pdf_section and has_first_publish:
                qualified_rows.append(parsed)
            else:
                fallback_rows.append(parsed)
            if len(qualified_rows) >= MIN_PER_POLLSTER:
                break

        if len(qualified_rows) < MIN_PER_POLLSTER:
            need = MIN_PER_POLLSTER - len(qualified_rows)
            qualified_rows.extend(fallback_rows[:need])

        per_pollster_counts[pollster] = len(qualified_rows)
        collected.extend(qualified_rows)

    # DoD 강제: 기관별 최소건수 충족 + 5기관 커버
    missing = {k: v for k, v in per_pollster_counts.items() if v < MIN_PER_POLLSTER}
    if missing:
        raise RuntimeError(f"insufficient samples per pollster: {missing}")
    if len(collected) < (MIN_PER_POLLSTER * len(TARGET_POLLSTERS)):
        raise RuntimeError(f"insufficient total samples: {len(collected)}")

    eval_payload = {
        **_evaluate(collected),
        "pollster_target_count": len(TARGET_POLLSTERS),
        "pollster_covered_count": sum(1 for v in per_pollster_counts.values() if v >= MIN_PER_POLLSTER),
        "per_pollster_counts": per_pollster_counts,
        "acceptance_checks": {
            "pollster_coverage_ge_5": sum(1 for v in per_pollster_counts.values() if v >= MIN_PER_POLLSTER) >= 5,
            "per_pollster_floor_met": not bool(missing),
            "total_sample_floor_met": len(collected) >= (MIN_PER_POLLSTER * len(TARGET_POLLSTERS)),
        },
    }

    # 내부 평가용 raw 필드 제거
    output_records = []
    for rec in collected:
        out = dict(rec)
        out.pop("_gold_result_items", None)
        out.pop("_html_rows", None)
        output_records.append(out)

    return {
        "data": {
            "run_type": "nesdc_pdf_adapter_v2_5pollsters",
            "extractor_version": "nesdc-pdf-adapter-v2-5pollsters",
            "records": output_records,
        },
        "eval": eval_payload,
    }


def main() -> None:
    out = generate_adapter_v2_5pollsters()

    Path(OUTPUT_DATA).write_text(json.dumps(out["data"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    Path(OUTPUT_EVAL).write_text(json.dumps(out["eval"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(out["eval"], ensure_ascii=False, indent=2))
    print("written:", OUTPUT_DATA)
    print("written:", OUTPUT_EVAL)


if __name__ == "__main__":
    main()
