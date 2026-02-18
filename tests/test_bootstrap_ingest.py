from __future__ import annotations

import json
from pathlib import Path

from app.jobs.bootstrap_ingest import build_summary, discover_payload_files, load_payload_documents


class FakeRepo:
    def __init__(self):
        self.run_id = 0
        self.review: list[tuple[str, str, str, str]] = []
        self.articles = {}
        self.observations = {}
        self.options = set()

    def create_ingestion_run(self, run_type, extractor_version, llm_model):  # noqa: ARG002
        self.run_id += 1
        return self.run_id

    def finish_ingestion_run(self, run_id, status, processed_count, error_count):  # noqa: ARG002
        return None

    def upsert_region(self, region):  # noqa: ARG002
        return None

    def upsert_matchup(self, matchup):
        if matchup["region_code"] == "99-999":
            raise RuntimeError("forced missing region")
        return None

    def upsert_candidate(self, candidate):  # noqa: ARG002
        return None

    def upsert_article(self, article):
        self.articles[article["url"]] = article
        return 1

    def upsert_poll_observation(self, observation, article_id, ingestion_run_id):  # noqa: ARG002
        self.observations[observation["observation_key"]] = observation
        return 1

    def upsert_poll_option(self, observation_id, option):
        self.options.add((observation_id, option["option_type"], option["option_name"], option.get("value_mid")))

    def insert_review_queue(self, entity_type, entity_id, issue_type, review_note):
        self.review.append((entity_type, entity_id, issue_type, review_note))

    def count_review_queue(self):
        return len(self.review)


def _write_payload(path: Path, *, region_code: str, observation_key: str) -> None:
    payload = {
        "run_type": "bootstrap",
        "extractor_version": "bootstrap-v1",
        "records": [
            {
                "article": {
                    "url": f"https://example.com/{observation_key}",
                    "title": "sample",
                    "publisher": "pub",
                },
                "region": (
                    {
                        "region_code": region_code,
                        "sido_name": "서울특별시",
                        "sigungu_name": "전체",
                        "admin_level": "sido",
                    }
                    if region_code != "99-999"
                    else None
                ),
                "observation": {
                    "observation_key": observation_key,
                    "survey_name": "survey",
                    "pollster": "MBC",
                    "region_code": region_code,
                    "office_type": "광역자치단체장",
                    "matchup_id": f"20260603|광역자치단체장|{region_code}",
                },
                "options": [
                    {
                        "option_type": "candidate_matchup",
                        "option_name": "A",
                        "value_raw": "40%",
                    }
                ],
            }
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_discover_payload_files_for_file_and_directory(tmp_path: Path):
    file_one = tmp_path / "one.json"
    file_two = tmp_path / "two.json"
    file_one.write_text("{}", encoding="utf-8")
    file_two.write_text("{}", encoding="utf-8")

    single = discover_payload_files(file_one)
    assert single == [file_one]

    multiple = discover_payload_files(tmp_path)
    assert multiple == [file_one, file_two]


def test_build_summary_counts_success_fail_and_review_queue(tmp_path: Path):
    ok_file = tmp_path / "ok.json"
    fail_file = tmp_path / "fail.json"
    _write_payload(ok_file, region_code="11-000", observation_key="obs-ok")
    _write_payload(fail_file, region_code="99-999", observation_key="obs-fail")

    docs = []
    docs.extend(load_payload_documents(ok_file))
    docs.extend(load_payload_documents(fail_file))

    repo = FakeRepo()
    summary = build_summary(docs, repo, input_path=str(tmp_path))

    assert summary["total"] == 2
    assert summary["success"] == 1
    assert summary["fail"] == 1
    assert summary["review_queue_count"] == 1
    assert summary["run_count"] == 2
