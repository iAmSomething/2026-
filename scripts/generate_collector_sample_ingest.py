from __future__ import annotations

import json
from pathlib import Path

from app.models.schemas import IngestPayload
from src.pipeline.collector import CollectorOutput, PollCollector
from src.pipeline.contracts import Article, stable_id
from src.pipeline.ingest_adapter import collector_output_to_ingest_payload


SAMPLE_ARTICLES: list[dict[str, str]] = [
    {
        "url": "https://example.com/poll/1",
        "title": "서울시장 가상대결 조사",
        "text": "서울시장 여론조사 KBS 결과 정원오 44% vs 오세훈 31%, 표본오차 ±3.1%",
    },
    {
        "url": "https://example.com/poll/2",
        "title": "부산시장 양자대결",
        "text": "부산시장 여론조사 MBC 발표 김영춘 41% vs 박형준 39%, 응답률 12.5%",
    },
    {
        "url": "https://example.com/poll/3",
        "title": "경기지사 조사",
        "text": "경기지사 여론조사 SBS 결과 김동연 46% vs 유승민 35%",
    },
    {
        "url": "https://example.com/poll/4",
        "title": "인천 교육감 여론조사",
        "text": "인천 교육감 여론조사 한국갤럽 발표 이학재 38% vs 김교흥 33%",
    },
    {
        "url": "https://example.com/poll/5",
        "title": "제주 재보궐 조사",
        "text": "제주 재보궐 여론조사 리얼미터 결과 고희범 37% vs 허향진 34%",
    },
]


def build_output() -> CollectorOutput:
    collector = PollCollector(election_id="20260603")
    output = CollectorOutput()

    for sample in SAMPLE_ARTICLES:
        article = Article(
            id=stable_id("art", sample["url"]),
            url=sample["url"],
            title=sample["title"],
            publisher="샘플뉴스",
            published_at="2026-02-18T09:00:00+09:00",
            snippet=sample["text"][:120],
            collected_at="2026-02-18T00:00:00+00:00",
            raw_hash=stable_id("hash", sample["text"]),
            raw_text=sample["text"],
        )
        output.articles.append(article)
        observations, options, errors = collector.extract(article)
        output.poll_observations.extend(observations)
        output.poll_options.extend(options)
        output.review_queue.extend(errors)
    return output


def main() -> None:
    output = build_output()
    payload = collector_output_to_ingest_payload(
        output,
        run_type="manual",
        extractor_version="collector-freeze-v1",
    )
    # 백엔드 적재 계약과 완전 일치하는지 즉시 검증
    IngestPayload.model_validate(payload)

    out_path = Path("data/sample_ingest_collector_5.json")
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"written: {out_path}")
    print(f"records: {len(payload['records'])}")


if __name__ == "__main__":
    main()
