#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from app.db import get_connection
from app.services.repository import PostgresRepository
from src.pipeline.standards import COMMON_CODE_REGIONS

OUT_REGISTRY = Path("data/issue482_incumbent_registry_fallback.json")
OUT_REPORT = Path("data/issue482_incumbent_registry_fallback_report.json")
OUT_PUBLISH = Path("data/issue482_incumbent_registry_publish_result.json")

OFFICE_TYPES = ("광역자치단체장", "광역의회", "교육감")

# 광역단위 단체장/교육감 기본 시드. 일부 항목은 수동검수 플래그를 유지한다.
MAYOR_SEED: dict[str, dict[str, Any]] = {
    "11-000": {"incumbent_name": "오세훈", "party_name": "국민의힘", "term_seq": 2, "source_url": "https://www.seoul.go.kr"},
    "26-000": {"incumbent_name": "박형준", "party_name": "국민의힘", "term_seq": 1, "source_url": "https://www.busan.go.kr"},
    "27-000": {"incumbent_name": "홍준표", "party_name": "국민의힘", "term_seq": 1, "source_url": "https://www.daegu.go.kr"},
    "28-000": {"incumbent_name": "유정복", "party_name": "국민의힘", "term_seq": 2, "source_url": "https://www.incheon.go.kr"},
    "29-000": {"incumbent_name": "강기정", "party_name": "더불어민주당", "term_seq": 1, "source_url": "https://www.gwangju.go.kr"},
    "30-000": {"incumbent_name": "이장우", "party_name": "국민의힘", "term_seq": 1, "source_url": "https://www.daejeon.go.kr"},
    "31-000": {"incumbent_name": "김두겸", "party_name": "국민의힘", "term_seq": 1, "source_url": "https://www.ulsan.go.kr"},
    "36-000": {"incumbent_name": "최민호", "party_name": "국민의힘", "term_seq": 1, "source_url": "https://www.sejong.go.kr"},
    "41-000": {"incumbent_name": "김동연", "party_name": "더불어민주당", "term_seq": 1, "source_url": "https://www.gg.go.kr"},
    "42-000": {"incumbent_name": "김진태", "party_name": "국민의힘", "term_seq": 1, "source_url": "https://state.gwd.go.kr"},
    "43-000": {"incumbent_name": "김영환", "party_name": "국민의힘", "term_seq": 1, "source_url": "https://www.chungbuk.go.kr"},
    "44-000": {"incumbent_name": "김태흠", "party_name": "국민의힘", "term_seq": 1, "source_url": "https://www.chungnam.go.kr"},
    "45-000": {"incumbent_name": "김관영", "party_name": "더불어민주당", "term_seq": 1, "source_url": "https://www.jeonbuk.go.kr"},
    "46-000": {"incumbent_name": "김영록", "party_name": "더불어민주당", "term_seq": 2, "source_url": "https://www.jeonnam.go.kr"},
    "47-000": {"incumbent_name": "이철우", "party_name": "국민의힘", "term_seq": 2, "source_url": "https://www.gb.go.kr"},
    "48-000": {"incumbent_name": "박완수", "party_name": "국민의힘", "term_seq": 1, "source_url": "https://www.gyeongnam.go.kr"},
    "50-000": {"incumbent_name": "오영훈", "party_name": "더불어민주당", "term_seq": 1, "source_url": "https://www.jeju.go.kr"},
}

SUPERINTENDENT_SEED: dict[str, dict[str, Any]] = {
    "11-000": {"incumbent_name": "정근식", "party_name": None, "term_seq": 1, "source_url": "https://www.sen.go.kr"},
    "26-000": {"incumbent_name": "김석준", "party_name": None, "term_seq": 1, "source_url": "https://www.pen.go.kr"},
    "27-000": {"incumbent_name": "강은희", "party_name": None, "term_seq": 2, "source_url": "https://www.dge.go.kr"},
    "28-000": {"incumbent_name": "도성훈", "party_name": None, "term_seq": 2, "source_url": "https://www.ice.go.kr"},
    "29-000": {"incumbent_name": "이정선", "party_name": None, "term_seq": 1, "source_url": "https://www.gen.go.kr"},
    "30-000": {"incumbent_name": "설동호", "party_name": None, "term_seq": 3, "source_url": "https://www.dje.go.kr"},
    "31-000": {"incumbent_name": "천창수", "party_name": None, "term_seq": 1, "source_url": "https://www.use.go.kr"},
    "36-000": {"incumbent_name": "최교진", "party_name": None, "term_seq": 3, "source_url": "https://www.sje.go.kr"},
    "41-000": {"incumbent_name": "임태희", "party_name": None, "term_seq": 1, "source_url": "https://www.goe.go.kr"},
    "42-000": {"incumbent_name": "신경호", "party_name": None, "term_seq": 1, "source_url": "https://www.gwe.go.kr"},
    "43-000": {"incumbent_name": "윤건영", "party_name": None, "term_seq": 1, "source_url": "https://www.cbe.go.kr"},
    "44-000": {"incumbent_name": "김지철", "party_name": None, "term_seq": 3, "source_url": "https://www.cne.go.kr"},
    "45-000": {"incumbent_name": "서거석", "party_name": None, "term_seq": 1, "source_url": "https://www.jbe.go.kr"},
    "46-000": {"incumbent_name": "김대중", "party_name": None, "term_seq": 1, "source_url": "https://www.jne.go.kr"},
    "47-000": {"incumbent_name": "임종식", "party_name": None, "term_seq": 2, "source_url": "https://www.gbe.kr"},
    "48-000": {"incumbent_name": "박종훈", "party_name": None, "term_seq": 3, "source_url": "https://www.gne.go.kr"},
    "50-000": {"incumbent_name": "김광수", "party_name": None, "term_seq": 1, "source_url": "https://www.jje.go.kr"},
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sido_codes() -> list[str]:
    return sorted(code for code, meta in COMMON_CODE_REGIONS.items() if meta.admin_level == "sido")


def _term_limit_flag(office_type: str, term_seq: int | None) -> bool | None:
    if term_seq is None:
        return None
    if office_type in {"광역자치단체장", "교육감"}:
        return term_seq >= 3
    return None


def _build_council_placeholder(region_code: str) -> dict[str, Any]:
    meta = COMMON_CODE_REGIONS[region_code]
    base = str(meta.sido_name).replace("특별자치시", "").replace("특별시", "").replace("광역시", "").replace("특별자치도", "").replace("도", "")
    return {
        "incumbent_name": f"{base}광역의회 의장(확인필요)",
        "party_name": None,
        "term_seq": None,
        "source_url": "https://www.ncassembly.go.kr",
    }


def _build_registry_row(
    *,
    office_type: str,
    region_code: str,
    seed: dict[str, Any],
    updated_at: str,
) -> dict[str, Any]:
    term_seq_raw = seed.get("term_seq")
    term_seq = int(term_seq_raw) if term_seq_raw is not None else None
    term_limit_flag = _term_limit_flag(office_type, term_seq)

    needs_manual_review = bool(seed.get("needs_manual_review", False))
    if term_limit_flag is None:
        needs_manual_review = True

    return {
        "registry_id": f"incumbent|{office_type}|{region_code}",
        "office_type": office_type,
        "region_code": region_code,
        "incumbent_name": str(seed.get("incumbent_name") or "현직자확인필요"),
        "party_name": seed.get("party_name"),
        "term_seq": term_seq,
        "term_limit_flag": term_limit_flag,
        "needs_manual_review": needs_manual_review,
        "source_url": str(seed.get("source_url") or "https://www.nec.go.kr"),
        "updated_at": updated_at,
        "source_channel": "incumbent_registry",
    }


def build_registry_records() -> list[dict[str, Any]]:
    updated_at = _utc_now_iso()
    records: list[dict[str, Any]] = []
    for region_code in _sido_codes():
        mayor_seed = MAYOR_SEED.get(region_code, {"incumbent_name": "현직자확인필요", "party_name": None, "term_seq": None})
        superintendent_seed = SUPERINTENDENT_SEED.get(region_code, {"incumbent_name": "현직교육감확인필요", "party_name": None, "term_seq": None})
        council_seed = _build_council_placeholder(region_code)

        records.append(
            _build_registry_row(
                office_type="광역자치단체장",
                region_code=region_code,
                seed=mayor_seed,
                updated_at=updated_at,
            )
        )
        records.append(
            _build_registry_row(
                office_type="광역의회",
                region_code=region_code,
                seed=council_seed,
                updated_at=updated_at,
            )
        )
        records.append(
            _build_registry_row(
                office_type="교육감",
                region_code=region_code,
                seed=superintendent_seed,
                updated_at=updated_at,
            )
        )
    return records


def _acceptance_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    regional_count = len(_sido_codes())
    by_office: dict[str, int] = {office: 0 for office in OFFICE_TYPES}
    for row in records:
        office = str(row.get("office_type") or "")
        if office in by_office:
            by_office[office] += 1

    unresolved_terms = [
        row for row in records if row.get("term_limit_flag") is None and row.get("needs_manual_review") is not True
    ]
    source_mix = [row for row in records if row.get("source_channel") != "incumbent_registry"]
    duplicated_keys = len({row["registry_id"] for row in records}) != len(records)

    return {
        "regional_count": regional_count,
        "total_record_count": len(records),
        "by_office_count": by_office,
        "manual_review_count": sum(1 for row in records if row.get("needs_manual_review")),
        "term_limit_true_count": sum(1 for row in records if row.get("term_limit_flag") is True),
        "acceptance_checks": {
            "regional_coverage_no_missing": all(by_office[office] == regional_count for office in OFFICE_TYPES),
            "term_uncertainty_marked": len(unresolved_terms) == 0,
            "poll_observation_key_collision_zero": not duplicated_keys,
            "source_channel_separated": len(source_mix) == 0,
        },
    }


def publish_to_db(records: list[dict[str, Any]]) -> dict[str, Any]:
    upserted = 0
    with get_connection() as conn:
        repo = PostgresRepository(conn)
        for row in records:
            region_code = str(row["region_code"])
            meta = COMMON_CODE_REGIONS.get(region_code)
            if meta is not None:
                repo.upsert_region(
                    {
                        "region_code": meta.region_code,
                        "sido_name": meta.sido_name,
                        "sigungu_name": meta.sigungu_name,
                        "admin_level": meta.admin_level,
                        "parent_region_code": meta.parent_region_code,
                    }
                )
            repo.upsert_incumbent_registry(row)
            upserted += 1
    return {"upserted_count": upserted}


def run(
    *,
    registry_out: Path = OUT_REGISTRY,
    report_out: Path = OUT_REPORT,
    publish_out: Path = OUT_PUBLISH,
    apply_db: bool = False,
) -> dict[str, Any]:
    records = build_registry_records()
    report = _acceptance_report(records)

    registry_payload = {
        "issue": 482,
        "source_channel": "incumbent_registry",
        "records": records,
    }
    registry_out.write_text(json.dumps(registry_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    publish_result = {"applied": False, "upserted_count": 0}
    if apply_db:
        applied = publish_to_db(records)
        publish_result = {"applied": True, **applied}
    publish_out.write_text(json.dumps(publish_result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "registry_out": str(registry_out),
        "report_out": str(report_out),
        "publish_out": str(publish_out),
        "report": report,
        "publish_result": publish_result,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Issue #482 incumbent fallback registry builder")
    parser.add_argument("--registry-out", default=str(OUT_REGISTRY))
    parser.add_argument("--report-out", default=str(OUT_REPORT))
    parser.add_argument("--publish-out", default=str(OUT_PUBLISH))
    parser.add_argument("--apply-db", action="store_true")
    args = parser.parse_args()

    result = run(
        registry_out=Path(args.registry_out),
        report_out=Path(args.report_out),
        publish_out=Path(args.publish_out),
        apply_db=args.apply_db,
    )
    print(f"written: {result['registry_out']}")
    print(f"written: {result['report_out']}")
    print(f"written: {result['publish_out']}")
    print(f"regional_coverage_no_missing={result['report']['acceptance_checks']['regional_coverage_no_missing']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
