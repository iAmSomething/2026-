from __future__ import annotations

import json

from scripts.generate_collector_article_cutoff_cleanup_v1 import (
    apply_article_cutoff,
    build_backfill_cleanup_sql,
    generate_cleanup_outputs,
)


def test_apply_article_cutoff_rejects_only_records_before_cutoff():
    records = [
        {
            "article": {"published_at": "2025-11-30T23:59:59+09:00"},
            "observation": {"observation_key": "obs-old", "source_channel": "article", "source_channels": ["article"]},
        },
        {
            "article": {"published_at": None},
            "observation": {"observation_key": "obs-missing", "source_channel": "article", "source_channels": ["article"]},
        },
        {
            "article": {"published_at": None},
            "observation": {"observation_key": "obs-nesdc", "source_channel": "nesdc", "source_channels": ["nesdc"]},
        },
        {
            "article": {"published_at": "2025-12-01T00:00:00+09:00"},
            "observation": {"observation_key": "obs-pass", "source_channel": "article", "source_channels": ["article"]},
        },
    ]

    kept, rejected = apply_article_cutoff(records)

    assert len(kept) == 3
    assert len(rejected) == 1
    reasons = {row["reason"] for row in rejected}
    assert reasons == {"PUBLISHED_AT_BEFORE_CUTOFF"}


def test_build_backfill_cleanup_sql_contains_cutoff_where_clause():
    sql = build_backfill_cleanup_sql()
    assert "poll_observations" in sql["delete_poll_observations"]
    assert "articles" in sql["delete_orphan_articles"]
    assert "candidates" in sql["cleanup_candidates_article_published_at"]
    assert "cutoff" in sql["sql_params_example"]


def test_generate_cleanup_outputs_writes_filtered_payload_and_report(tmp_path):
    input_path = tmp_path / "input.json"
    filtered_path = tmp_path / "filtered.json"
    report_path = tmp_path / "report.json"
    input_payload = {
        "run_type": "manual",
        "extractor_version": "manual-v1",
        "records": [
            {
                "article": {"published_at": "2025-11-30T23:59:59+09:00"},
                "observation": {"observation_key": "obs-old", "source_channel": "article", "source_channels": ["article"]},
                "options": [],
            },
            {
                "article": {"published_at": "2025-12-01T00:00:00+09:00"},
                "observation": {"observation_key": "obs-pass", "source_channel": "article", "source_channels": ["article"]},
                "options": [],
            },
        ],
    }
    input_path.write_text(json.dumps(input_payload, ensure_ascii=False), encoding="utf-8")

    report = generate_cleanup_outputs(
        input_path=str(input_path),
        filtered_output_path=str(filtered_path),
        report_output_path=str(report_path),
    )

    assert report["counts"]["input_record_count"] == 2
    assert report["counts"]["kept_record_count"] == 1
    assert report["counts"]["cutoff_violation_count"] == 1

    filtered = json.loads(filtered_path.read_text(encoding="utf-8"))
    assert len(filtered["records"]) == 1
    assert filtered["records"][0]["observation"]["observation_key"] == "obs-pass"
