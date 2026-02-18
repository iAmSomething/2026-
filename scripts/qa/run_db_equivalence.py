#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import psycopg
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.main import app  # noqa: E402
from app.models.schemas import IngestPayload  # noqa: E402
from app.services.ingest_service import ingest_payload  # noqa: E402
from app.services.repository import PostgresRepository  # noqa: E402
from scripts.init_db import run_schema  # noqa: E402


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def redact_dsn(dsn: str) -> str:
    parsed = urlparse(dsn)
    host = parsed.hostname or "unknown-host"
    port = parsed.port or "default"
    db = parsed.path.lstrip("/") or "postgres"
    return f"{parsed.scheme}://***@{host}:{port}/{db}"


def classify_failure(stage: str, exc: Exception) -> str:
    message = str(exc).lower()
    if "authentication failed" in message or "permission denied" in message or "insufficient privilege" in message:
        return "permission"
    if isinstance(exc, psycopg.OperationalError) or "timeout" in message or "could not connect" in message:
        return "network"
    if stage.startswith("schema") or "relation" in message:
        return "schema"
    if isinstance(exc, AssertionError):
        return "data"
    return "data"


def resolve_database_url(target: str) -> str:
    if target == "remote":
        db_url = os.getenv("REMOTE_DATABASE_URL") or os.getenv("DATABASE_URL")
    else:
        db_url = os.getenv("LOCAL_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL or target-specific DB URL is required")
    return db_url


def ensure_runtime_env(db_url: str) -> None:
    os.environ["DATABASE_URL"] = db_url
    os.environ.setdefault("SUPABASE_URL", "https://local.test")
    os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "local-service-role")
    os.environ.setdefault("DATA_GO_KR_KEY", "local-data-go-key")
    os.environ.setdefault("INTERNAL_JOB_TOKEN", "local-internal-token")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DB equivalence verification (local/remote)")
    parser.add_argument("--target", choices=["local", "remote"], default="remote")
    parser.add_argument("--input", default="data/sample_ingest.json")
    parser.add_argument("--report", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db_url = resolve_database_url(args.target)
    ensure_runtime_env(db_url)

    report_path = args.report or f"data/qa_{args.target}_db_report.json"
    report: dict = {
        "target": args.target,
        "started_at": now_utc(),
        "database_url": redact_dsn(db_url),
        "input": args.input,
        "status": "running",
        "stages": [],
    }

    stage = "init"
    try:
        stage = "schema_apply"
        run_schema(Path(ROOT / "db" / "schema.sql"))
        report["stages"].append({"name": stage, "status": "ok"})

        stage = "load_payload"
        payload_data = json.loads(Path(args.input).read_text(encoding="utf-8"))
        payload = IngestPayload.model_validate(payload_data)
        report["stages"].append({"name": stage, "status": "ok", "records": len(payload.records)})

        stage = "ingest_first_run"
        with psycopg.connect(db_url, row_factory=psycopg.rows.dict_row) as conn:
            repo = PostgresRepository(conn)
            first = ingest_payload(payload, repo)
        report["stages"].append({"name": stage, "status": "ok", "result": first.__dict__})

        stage = "ingest_second_run"
        with psycopg.connect(db_url, row_factory=psycopg.rows.dict_row) as conn:
            repo = PostgresRepository(conn)
            second = ingest_payload(payload, repo)
        report["stages"].append({"name": stage, "status": "ok", "result": second.__dict__})

        stage = "db_checks"
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*), count(DISTINCT url) FROM articles")
                a_total, a_dist = cur.fetchone()
                assert a_total == a_dist

                cur.execute("SELECT count(*), count(DISTINCT observation_key) FROM poll_observations")
                o_total, o_dist = cur.fetchone()
                assert o_total == o_dist

                cur.execute("SELECT count(*) FROM ingestion_runs")
                ingestion_runs = cur.fetchone()[0]
                assert ingestion_runs >= 2

                cur.execute(
                    """
                    SELECT value_min, value_max, value_mid
                    FROM poll_options
                    WHERE value_raw='53~55%'
                    LIMIT 1
                    """
                )
                normalized = cur.fetchone()
                assert normalized is not None
                assert float(normalized[0]) == 53.0
                assert float(normalized[1]) == 55.0
                assert float(normalized[2]) == 54.0

        report["stages"].append(
            {
                "name": stage,
                "status": "ok",
                "counts": {
                    "articles_total": int(a_total),
                    "observations_total": int(o_total),
                    "ingestion_runs": int(ingestion_runs),
                },
            }
        )

        stage = "api_checks"
        sample_candidate = "cand-jwo"
        sample_region_query = "서울"
        if payload.records:
            record = payload.records[0]
            if record.candidates:
                sample_candidate = record.candidates[0].candidate_id
            if record.region:
                sample_region_query = record.region.sido_name or sample_region_query

        with TestClient(app) as client:
            summary = client.get("/api/v1/dashboard/summary")
            assert summary.status_code == 200
            summary_json = summary.json()
            assert "party_support" in summary_json
            assert "presidential_approval" in summary_json

            regions = client.get("/api/v1/regions/search", params={"q": sample_region_query})
            assert regions.status_code == 200
            regions_json = regions.json()
            assert isinstance(regions_json, list)

            candidate = client.get(f"/api/v1/candidates/{sample_candidate}")
            assert candidate.status_code == 200
            candidate_json = candidate.json()
            assert "candidate_id" in candidate_json
            assert "name_ko" in candidate_json

        report["stages"].append(
            {
                "name": stage,
                "status": "ok",
                "api_contract": {
                    "summary_keys": list(summary_json.keys()),
                    "regions_count": len(regions_json),
                    "candidate_id": candidate_json["candidate_id"],
                },
            }
        )

        report["status"] = "success"
        report["finished_at"] = now_utc()
        Path(report_path).parent.mkdir(parents=True, exist_ok=True)
        Path(report_path).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": "success", "report": report_path}, ensure_ascii=False))
        return 0

    except Exception as exc:  # noqa: BLE001
        report["status"] = "failed"
        report["failed_stage"] = stage
        report["failure_type"] = classify_failure(stage, exc)
        report["error"] = str(exc)
        report["finished_at"] = now_utc()
        Path(report_path).parent.mkdir(parents=True, exist_ok=True)
        Path(report_path).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": "failed", "report": report_path, "stage": stage, "error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
