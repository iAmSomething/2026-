from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
import io
import os
from pathlib import Path
import sys
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import get_connection  # noqa: E402
from scripts.sync_elections_master import run_elections_master_sync  # noqa: E402
from src.pipeline.standards import COMMON_CODE_REGIONS  # noqa: E402

SIDO_ALIAS = {
    "강원도": "강원특별자치도",
    "전라북도": "전북특별자치도",
    "제주도": "제주특별자치도",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Issue #312 운영 DB CommonCodeService 전수 재동기화(지역+elections 슬롯) 실행 스크립트"
    )
    parser.add_argument("--sg-id", default="20260603", help="CommonCodeService 선거ID")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report-path", default="data/issue312_sync_report.json")
    parser.add_argument("--pre-snapshot-path", default="data/issue312_pre_snapshot.json")
    parser.add_argument("--post-snapshot-path", default="data/issue312_post_snapshot.json")
    parser.add_argument("--compare-path", default="data/issue312_sync_before_after.json")
    parser.add_argument("--elections-report-path", default="data/elections_master_sync_report_issue312.json")
    return parser.parse_args()


def _write_json(path: str | Path, payload: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _normalize_sido_name(value: Any) -> str:
    raw = str(value or "").strip()
    return SIDO_ALIAS.get(raw, raw)


def _normalize_sigungu_name(value: Any) -> str:
    return str(value or "").strip().replace(" ", "")


def _common_sgg_rows(*, sg_id: str, sg_typecode: str, service_key: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    page_no = 1
    while True:
        params = {
            "serviceKey": service_key,
            "sgId": sg_id,
            "sgTypecode": sg_typecode,
            "pageNo": str(page_no),
            "numOfRows": "100",
            "resultType": "json",
        }
        url = "https://apis.data.go.kr/9760000/CommonCodeService/getCommonSggCodeList?" + urlencode(params)
        with urlopen(url, timeout=10) as resp:
            payload = json.loads(resp.read().decode(resp.headers.get_content_charset() or "utf-8", "replace"))
        body = ((payload.get("response") or {}).get("body") or {}) if isinstance(payload, dict) else {}
        items = (body.get("items") or {}).get("item", [])
        if isinstance(items, dict):
            items = [items]
        if not items:
            break
        out.extend([dict(x) for x in items if isinstance(x, dict)])
        total_count = int(body.get("totalCount") or 0)
        if total_count and len(out) >= total_count:
            break
        page_no += 1
        if page_no > 40:
            break
    return out


def _region_lookup_from_standards() -> tuple[dict[str, str], dict[tuple[str, str], str]]:
    sido_code_by_name: dict[str, str] = {}
    sig_code_by_name: dict[tuple[str, str], str] = {}
    for meta in COMMON_CODE_REGIONS.values():
        sd = _normalize_sido_name(meta.sido_name)
        if meta.admin_level == "sido":
            sido_code_by_name.setdefault(sd, meta.region_code)
            continue
        sg = _normalize_sigungu_name(meta.sigungu_name)
        sig_code_by_name.setdefault((sd, sg), meta.region_code)
    return sido_code_by_name, sig_code_by_name


def _region_lookup_from_tsv(
    *,
    allowed_prefixes: set[str],
) -> tuple[dict[str, str], dict[tuple[str, str], str]]:
    tsv_url = (
        "https://raw.githubusercontent.com/vuski/admdongkor/master/"
        "%ED%86%B5%EA%B3%84%EC%B2%ADMDIS%EC%9D%B8%EA%B5%AC%EC%9A%A9_%ED%96%89%EC%A0%95%EA%B2%BD%EA%B3%84%EC%A4%91%EC%8B%AC%EC%A0%90/"
        "coordinate_UTMK_%EC%9D%B4%EB%A6%84%ED%8F%AC%ED%95%A8.tsv"
    )
    with urlopen(tsv_url, timeout=30) as resp:
        text = resp.read().decode(resp.headers.get_content_charset() or "utf-8", "replace")

    sido_code_by_name: dict[str, str] = {}
    sig_code_by_name: dict[tuple[str, str], str] = {}
    rows = csv.DictReader(io.StringIO(text), delimiter="\t")
    for row in rows:
        adm_code = str(row.get("ADMCD") or "").strip()
        adm_name = str(row.get("ADMNM") or "").strip()
        if len(adm_code) != 10 or not adm_code.isdigit() or not adm_name:
            continue
        prefix = adm_code[:2]
        if prefix not in allowed_prefixes:
            continue

        if adm_code.endswith("00000000"):
            sido_code_by_name[_normalize_sido_name(adm_name)] = f"{prefix}-000"
            continue

        if not adm_code.endswith("00000"):
            continue

        parts = adm_name.split()
        if len(parts) < 2:
            continue
        sido_name = _normalize_sido_name(parts[0])
        sigungu_name = _normalize_sigungu_name(" ".join(parts[1:]))
        if not sigungu_name:
            continue
        sig_code_by_name[(sido_name, sigungu_name)] = f"{prefix}-{adm_code[2:5]}"

    return sido_code_by_name, sig_code_by_name


def _region_lookup_from_db(conn) -> tuple[dict[str, str], dict[tuple[str, str], str]]:
    sido_code_by_name: dict[str, str] = {}
    sig_code_by_name: dict[tuple[str, str], str] = {}
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT region_code, sido_name, sigungu_name, admin_level
            FROM regions
            """
        )
        rows = cur.fetchall() or []
    for row in rows:
        code = str(row["region_code"] or "").strip()
        sd = _normalize_sido_name(row.get("sido_name"))
        sg = _normalize_sigungu_name(row.get("sigungu_name"))
        level = str(row.get("admin_level") or "").strip().lower()
        if not code or not sd:
            continue
        if level == "sido":
            sido_code_by_name.setdefault(sd, code)
            continue
        if level == "sigungu" and sg and sg != "전체":
            sig_code_by_name.setdefault((sd, sg), code)
    return sido_code_by_name, sig_code_by_name


def _suffix_set_by_prefix(codes: set[str]) -> dict[str, set[int]]:
    out: dict[str, set[int]] = {}
    for code in codes:
        if not isinstance(code, str) or "-" not in code:
            continue
        prefix, suffix = code.split("-", 1)
        if not suffix.isdigit():
            continue
        out.setdefault(prefix, set()).add(int(suffix))
    return out


def _allocate_generated_code(prefix: str, used_suffixes: set[int]) -> str:
    for suffix in range(900, 1000):
        if suffix not in used_suffixes:
            used_suffixes.add(suffix)
            return f"{prefix}-{suffix:03d}"
    for suffix in range(1, 900):
        if suffix not in used_suffixes:
            used_suffixes.add(suffix)
            return f"{prefix}-{suffix:03d}"
    raise RuntimeError(f"no available generated suffix for prefix={prefix}")


def _build_region_rows(
    *,
    common_sido_rows: list[dict[str, Any]],
    common_sig_rows: list[dict[str, Any]],
    db_sido_map: dict[str, str],
    db_sig_map: dict[tuple[str, str], str],
    std_sido_map: dict[str, str],
    std_sig_map: dict[tuple[str, str], str],
    tsv_sido_map: dict[str, str],
    tsv_sig_map: dict[tuple[str, str], str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows_by_code: dict[str, dict[str, Any]] = {}
    mapping_stats = {
        "mapped_from_db_count": 0,
        "mapped_from_standard_count": 0,
        "mapped_from_tsv_count": 0,
        "generated_code_count": 0,
        "missing_sido_names": [],
        "generated_examples": [],
    }

    used_codes: set[str] = set()
    used_suffixes = _suffix_set_by_prefix(set(db_sido_map.values()) | set(db_sig_map.values()) | set(std_sig_map.values()))

    def resolve_sido_code(sido_name: str) -> tuple[str | None, str]:
        if sido_name in db_sido_map:
            return db_sido_map[sido_name], "db"
        if sido_name in std_sido_map:
            return std_sido_map[sido_name], "standard"
        if sido_name in tsv_sido_map:
            return tsv_sido_map[sido_name], "tsv"
        return None, "missing"

    def append_row(row: dict[str, Any]) -> None:
        rows_by_code[row["region_code"]] = row
        used_codes.add(row["region_code"])

    # 1) 시도 rows
    for item in common_sido_rows:
        raw_sido_name = str(item.get("sdName") or item.get("sggName") or "").strip()
        if not raw_sido_name:
            continue
        sido_name = _normalize_sido_name(raw_sido_name)
        sido_code, source = resolve_sido_code(sido_name)
        if not sido_code:
            mapping_stats["missing_sido_names"].append(sido_name)
            continue
        if source == "db":
            mapping_stats["mapped_from_db_count"] += 1
        elif source == "standard":
            mapping_stats["mapped_from_standard_count"] += 1
        else:
            mapping_stats["mapped_from_tsv_count"] += 1

        append_row(
            {
                "region_code": sido_code,
                "sido_name": sido_name,
                "sigungu_name": "전체",
                "admin_level": "sido",
                "parent_region_code": None,
            }
        )

    # 2) 시군구 rows
    for item in common_sig_rows:
        raw_sido_name = str(item.get("sdName") or "").strip()
        raw_sig_name = str(item.get("wiwName") or item.get("sggName") or "").strip()
        if not raw_sido_name or not raw_sig_name:
            continue

        sido_name = _normalize_sido_name(raw_sido_name)
        sig_name = _normalize_sigungu_name(raw_sig_name)
        if not sig_name:
            continue

        sido_code, source = resolve_sido_code(sido_name)
        if not sido_code:
            continue
        if source == "db":
            mapping_stats["mapped_from_db_count"] += 1
        elif source == "standard":
            mapping_stats["mapped_from_standard_count"] += 1
        elif source == "tsv":
            mapping_stats["mapped_from_tsv_count"] += 1

        mapped_code = db_sig_map.get((sido_name, sig_name))
        mapped_source = "db"
        if not mapped_code:
            mapped_code = std_sig_map.get((sido_name, sig_name))
            mapped_source = "standard"
        if not mapped_code:
            mapped_code = tsv_sig_map.get((sido_name, sig_name))
            mapped_source = "tsv"

        if mapped_code and mapped_code not in rows_by_code:
            if mapped_source == "db":
                mapping_stats["mapped_from_db_count"] += 1
            elif mapped_source == "standard":
                mapping_stats["mapped_from_standard_count"] += 1
            else:
                mapping_stats["mapped_from_tsv_count"] += 1
            region_code = mapped_code
        elif mapped_code and mapped_code in rows_by_code:
            # 동일 코드가 이미 다른 이름으로 들어온 경우 generated로 우회
            prefix = sido_code[:2]
            region_code = _allocate_generated_code(prefix, used_suffixes.setdefault(prefix, set()))
            mapping_stats["generated_code_count"] += 1
            if len(mapping_stats["generated_examples"]) < 20:
                mapping_stats["generated_examples"].append(
                    {
                        "sido_name": sido_name,
                        "sigungu_name": raw_sig_name,
                        "generated_region_code": region_code,
                        "reason": "mapped_code_collision",
                    }
                )
        else:
            prefix = sido_code[:2]
            region_code = _allocate_generated_code(prefix, used_suffixes.setdefault(prefix, set()))
            mapping_stats["generated_code_count"] += 1
            if len(mapping_stats["generated_examples"]) < 20:
                mapping_stats["generated_examples"].append(
                    {
                        "sido_name": sido_name,
                        "sigungu_name": raw_sig_name,
                        "generated_region_code": region_code,
                        "reason": "name_not_in_lookup",
                    }
                )

        append_row(
            {
                "region_code": region_code,
                "sido_name": sido_name,
                "sigungu_name": raw_sig_name,
                "admin_level": "sigungu",
                "parent_region_code": sido_code,
            }
        )

    out_rows = sorted(
        rows_by_code.values(),
        key=lambda x: (
            0 if x["admin_level"] == "sido" else 1,
            x["region_code"],
        ),
    )
    mapping_stats["missing_sido_names"] = sorted(set(mapping_stats["missing_sido_names"]))
    mapping_stats["resolved_total"] = len(out_rows)
    return out_rows, mapping_stats


def _upsert_regions(conn, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO regions (region_code, sido_name, sigungu_name, admin_level, parent_region_code)
            VALUES (%(region_code)s, %(sido_name)s, %(sigungu_name)s, %(admin_level)s, %(parent_region_code)s)
            ON CONFLICT (region_code) DO UPDATE
            SET sido_name=EXCLUDED.sido_name,
                sigungu_name=EXCLUDED.sigungu_name,
                admin_level=EXCLUDED.admin_level,
                parent_region_code=EXCLUDED.parent_region_code,
                updated_at=NOW()
            """,
            rows,
        )
    conn.commit()
    return len(rows)


def _ensure_elections_master_schema(conn) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            """
            ALTER TABLE elections
                ADD COLUMN IF NOT EXISTS region_code TEXT,
                ADD COLUMN IF NOT EXISTS office_type TEXT,
                ADD COLUMN IF NOT EXISTS slot_matchup_id TEXT,
                ADD COLUMN IF NOT EXISTS title TEXT,
                ADD COLUMN IF NOT EXISTS source TEXT,
                ADD COLUMN IF NOT EXISTS has_poll_data BOOLEAN,
                ADD COLUMN IF NOT EXISTS latest_matchup_id TEXT,
                ADD COLUMN IF NOT EXISTS is_active BOOLEAN
            """
        )
        cur.execute(
            """
            ALTER TABLE elections
                ALTER COLUMN source SET DEFAULT 'code_master',
                ALTER COLUMN has_poll_data SET DEFAULT FALSE,
                ALTER COLUMN is_active SET DEFAULT TRUE
            """
        )
        cur.execute(
            """
            UPDATE elections
            SET source = COALESCE(source, 'code_master'),
                has_poll_data = COALESCE(has_poll_data, FALSE),
                is_active = COALESCE(is_active, TRUE)
            """
        )
        cur.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_elections_region_office_unique
            ON elections (region_code, office_type)
            """
        )
    conn.commit()
    return {"status": "ok"}


def _elections_master_columns_ready(conn) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*)::int AS cnt
            FROM information_schema.columns
            WHERE table_schema='public'
              AND table_name='elections'
              AND column_name IN (
                'region_code', 'office_type', 'slot_matchup_id',
                'title', 'source', 'has_poll_data', 'latest_matchup_id', 'is_active'
              )
            """
        )
        row = cur.fetchone() or {}
    return int(row.get("cnt", 0) or 0) == 8


def _db_snapshot(conn) -> dict[str, Any]:
    out: dict[str, Any] = {}
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT admin_level, COUNT(*)::int AS cnt
            FROM regions
            GROUP BY admin_level
            ORDER BY admin_level
            """
        )
        out["regions_by_level"] = {row["admin_level"]: row["cnt"] for row in (cur.fetchall() or [])}
        cur.execute("SELECT COUNT(*)::int AS cnt FROM regions")
        out["regions_total"] = int((cur.fetchone() or {}).get("cnt", 0) or 0)

        out["elections_master_columns_ready"] = _elections_master_columns_ready(conn)

        sample_codes = ["42-000", "11-000", "26-710"]
        samples: dict[str, dict[str, Any] | None] = {}
        for code in sample_codes:
            cur.execute(
                """
                SELECT region_code, sido_name, sigungu_name, admin_level, parent_region_code
                FROM regions
                WHERE region_code = %s
                """,
                (code,),
            )
            row = cur.fetchone()
            samples[code] = dict(row) if row else None
        out["region_samples"] = samples

        if out["elections_master_columns_ready"]:
            cur.execute("SELECT COUNT(*)::int AS cnt FROM elections")
            out["elections_total"] = int((cur.fetchone() or {}).get("cnt", 0) or 0)
            cur.execute(
                """
                SELECT region_code, office_type, slot_matchup_id, latest_matchup_id, has_poll_data, source, is_active
                FROM elections
                WHERE region_code IN ('42-000', '11-000', '26-710')
                ORDER BY region_code, office_type
                LIMIT 60
                """
            )
            out["election_samples"] = [dict(x) for x in (cur.fetchall() or [])]
        else:
            out["elections_total"] = None
            out["election_samples"] = []
    return out


def main() -> None:
    args = parse_args()
    service_key = os.getenv("DATA_GO_KR_KEY", "").strip()
    if not service_key:
        raise SystemExit("[FAIL] DATA_GO_KR_KEY is empty")

    with get_connection() as conn:
        pre_snapshot = _db_snapshot(conn)
        _write_json(args.pre_snapshot_path, pre_snapshot)

        common_sido_rows = _common_sgg_rows(sg_id=args.sg_id, sg_typecode="3", service_key=service_key)
        common_sig_rows = _common_sgg_rows(sg_id=args.sg_id, sg_typecode="4", service_key=service_key)
        common_sido_names = sorted(
            {
                _normalize_sido_name(str(row.get("sdName") or row.get("sggName") or "").strip())
                for row in common_sido_rows
                if str(row.get("sdName") or row.get("sggName") or "").strip()
            }
        )
        common_sig_names = sorted(
            {
                (
                    _normalize_sido_name(str(row.get("sdName") or "").strip()),
                    _normalize_sigungu_name(str(row.get("wiwName") or row.get("sggName") or "").strip()),
                )
                for row in common_sig_rows
                if str(row.get("sdName") or "").strip() and str(row.get("wiwName") or row.get("sggName") or "").strip()
            }
        )

        db_sido_map, db_sig_map = _region_lookup_from_db(conn)
        std_sido_map, std_sig_map = _region_lookup_from_standards()
        allowed_prefixes = {code.split("-", 1)[0] for code in std_sido_map.values()}
        tsv_sido_map, tsv_sig_map = _region_lookup_from_tsv(allowed_prefixes=allowed_prefixes)
        region_rows, mapping_stats = _build_region_rows(
            common_sido_rows=common_sido_rows,
            common_sig_rows=common_sig_rows,
            db_sido_map=db_sido_map,
            db_sig_map=db_sig_map,
            std_sido_map=std_sido_map,
            std_sig_map=std_sig_map,
            tsv_sido_map=tsv_sido_map,
            tsv_sig_map=tsv_sig_map,
        )

        expected_total = len(common_sido_names) + len(common_sig_names)
        built_total = len(region_rows)
        unresolved_count = max(expected_total - built_total, 0)

        upserted_region_count = 0
        schema_patch_result = {"status": "skipped"}
        elections_sync_result: dict[str, Any] = {"status": "skipped"}
        if not args.dry_run:
            upserted_region_count = _upsert_regions(conn, region_rows)
            schema_patch_result = _ensure_elections_master_schema(conn)
            elections_sync_result = run_elections_master_sync(
                dry_run=False,
                report_path=args.elections_report_path,
            )

        post_snapshot = _db_snapshot(conn)
        _write_json(args.post_snapshot_path, post_snapshot)

    compare_payload = {
        "pre": pre_snapshot,
        "post": post_snapshot,
        "delta": {
            "regions_total": (post_snapshot.get("regions_total") or 0) - (pre_snapshot.get("regions_total") or 0),
            "sido_count": int((post_snapshot.get("regions_by_level") or {}).get("sido", 0))
            - int((pre_snapshot.get("regions_by_level") or {}).get("sido", 0)),
            "sigungu_count": int((post_snapshot.get("regions_by_level") or {}).get("sigungu", 0))
            - int((pre_snapshot.get("regions_by_level") or {}).get("sigungu", 0)),
        },
    }
    _write_json(args.compare_path, compare_payload)

    report = {
        "status": "success",
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": args.dry_run,
        "sg_id": args.sg_id,
        "common_code_counts": {
            "sido_count": len(common_sido_names),
            "sigungu_count": len(common_sig_names),
            "total_expected": expected_total,
        },
        "resolved_region_rows": built_total,
        "unresolved_count": unresolved_count,
        "upserted_region_count": upserted_region_count,
        "mapping_stats": mapping_stats,
        "schema_patch": schema_patch_result,
        "elections_sync": elections_sync_result,
        "artifacts": {
            "pre_snapshot_path": args.pre_snapshot_path,
            "post_snapshot_path": args.post_snapshot_path,
            "compare_path": args.compare_path,
            "elections_report_path": args.elections_report_path,
        },
        "sample_checks": {
            "region_42_000_exists": post_snapshot.get("region_samples", {}).get("42-000") is not None,
            "region_11_000_exists": post_snapshot.get("region_samples", {}).get("11-000") is not None,
            "region_26_710_exists": post_snapshot.get("region_samples", {}).get("26-710") is not None,
            "regions_missing_zero": unresolved_count == 0,
        },
        "pm_required_cardinality": {
            "pre_regions_by_level": pre_snapshot.get("regions_by_level"),
            "post_regions_by_level": post_snapshot.get("regions_by_level"),
        },
        "pm_required_missing_codes": {
            "missing_sido_names": mapping_stats.get("missing_sido_names", []),
            "generated_code_examples": mapping_stats.get("generated_examples", []),
        },
        "pm_required_314_compare_case": {
            "before_master_rows_empty": int(pre_snapshot.get("elections_total") or 0) == 0,
            "after_master_rows_available": int(post_snapshot.get("elections_total") or 0) > 0
            if post_snapshot.get("elections_total") is not None
            else False,
            "before_regions_total": pre_snapshot.get("regions_total"),
            "after_regions_total": post_snapshot.get("regions_total"),
        },
    }
    _write_json(args.report_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
