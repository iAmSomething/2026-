from __future__ import annotations

import json
from pathlib import Path

from src.pipeline.collector import PollCollector
from src.pipeline.contracts import Article, stable_id


def build_samples() -> list[dict]:
    # 최소 30건 샘플 검증
    pairs = [
        ("정원오", "오세훈"),
        ("김영춘", "박형준"),
        ("김동연", "유승민"),
        ("이학재", "김교흥"),
        ("고희범", "허향진"),
        ("김경수", "박완수"),
        ("이재명", "남경필"),
        ("송하진", "김관영"),
        ("이용섭", "강기정"),
        ("김진태", "최문순"),
    ]
    regions = [
        "서울시장",
        "부산시장",
        "경기지사",
        "인천시장",
        "제주지사",
        "경남지사",
    ]

    samples: list[dict] = []
    idx = 0
    for i in range(30):
        a_name, b_name = pairs[i % len(pairs)]
        a_val = 30 + (i % 20)
        b_val = 20 + ((i * 3) % 20)
        region = regions[i % len(regions)]
        text = (
            f"{region} 여론조사 결과 조사기관 KBS 발표 "
            f"{a_name} {a_val}% vs {b_name} {b_val}% "
            f"표본오차 ±3.1%"
        )
        samples.append(
            {
                "id": idx,
                "text": text,
                "expected": {
                    (a_name, f"{a_val}%"),
                    (b_name, f"{b_val}%"),
                },
            }
        )
        idx += 1
    return samples


def evaluate() -> dict:
    collector = PollCollector(election_id="20260603")
    samples = build_samples()
    true_positive = 0
    predicted_total = 0
    expected_total = 0
    failed_cases: list[dict] = []

    for sample in samples:
        article = Article(
            id=stable_id("art", f"sample-{sample['id']}"),
            url=f"https://example.com/precision/{sample['id']}",
            title="정밀도 점검 샘플",
            publisher="샘플뉴스",
            published_at="2026-02-18T00:00:00+09:00",
            snippet=sample["text"][:120],
            collected_at="2026-02-18T00:00:00+00:00",
            raw_hash=stable_id("hash", sample["text"]),
            raw_text=sample["text"],
        )
        _observations, options, _errors = collector.extract(article)
        predicted = {(o.option_name, o.value_raw) for o in options if o.option_type == "candidate"}
        expected = sample["expected"]
        inter = predicted & expected

        true_positive += len(inter)
        predicted_total += len(predicted)
        expected_total += len(expected)
        if predicted != expected:
            failed_cases.append(
                {
                    "sample_id": sample["id"],
                    "expected": sorted([list(x) for x in expected]),
                    "predicted": sorted([list(x) for x in predicted]),
                }
            )

    precision = true_positive / predicted_total if predicted_total else 0.0
    recall = true_positive / expected_total if expected_total else 0.0
    return {
        "sample_count": len(samples),
        "true_positive": true_positive,
        "predicted_total": predicted_total,
        "expected_total": expected_total,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "failed_case_count": len(failed_cases),
        "failed_cases": failed_cases,
    }


def main() -> None:
    report = evaluate()
    path = Path("data/collector_precision_report.json")
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"written: {path}")


if __name__ == "__main__":
    main()
