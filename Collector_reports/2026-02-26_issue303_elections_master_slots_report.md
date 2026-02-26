# 2026-02-26 Issue #303 Elections Master Slots v1 Report

## 1. 대상 이슈
- Issue: #303 `[COLLECTOR][P1] 선거 마스터 생성 v1(region x office_type 기본슬롯 물리화)`
- URL: https://github.com/iAmSomething/2026-/issues/303

## 2. 구현 요약
- `elections` 마스터 테이블 신설(`db/schema.sql`):
  - 키: `(region_code, office_type)`
  - 주요 컬럼: `slot_matchup_id`, `source`, `has_poll_data`, `latest_matchup_id`, `is_active`
  - 기본 source: `code_master`
  - `has_poll_data=false`, `latest_matchup_id=null` 기본 허용
- region x office_type 슬롯 생성 규칙 구현(`app/services/elections_master.py`):
  - 광역(`admin_level=sido`): `광역자치단체장`, `광역의회`, `교육감`
  - 기초(`admin_level=sigungu`): `기초자치단체장`, `기초의회`
  - 재보궐 슬롯: 관측된 office_type(`%재보궐%`)이 있을 때만 추가
- 조회 경로 전환(`app/services/repository.py`):
  - `fetch_region_elections`가 `elections`를 1순위로 조회
  - fallback으로 기존 `matchups`/`poll_observations` 조회 유지
- 동기화 job 분리 + 연쇄 실행:
  - 신규 스크립트: `scripts/sync_elections_master.py`
  - `scripts/sync_common_codes.py` 실행 후 elections sync 연쇄 실행(옵션: `--skip-elections-sync`)
- 리포트 아티팩트:
  - `data/elections_master_sync_report.json`

## 3. 변경 파일
- 코드
  - `db/schema.sql`
  - `app/services/repository.py`
  - `app/services/elections_master.py`
  - `scripts/sync_elections_master.py`
  - `scripts/sync_common_codes.py`
- 테스트
  - `tests/test_elections_master.py`
  - `tests/test_sync_elections_master_script.py`
  - `tests/test_sync_common_codes_script.py`
  - `tests/test_schema_elections_master.py`
- 문서
  - `docs/04_DEPLOYMENT_AND_ENVIRONMENT.md`
  - `docs/06_COLLECTOR_CONTRACTS.md`

## 4. 검증 결과
- 실행:
  - `../election2026_codex/.venv/bin/pytest -q tests/test_elections_master.py tests/test_sync_elections_master_script.py tests/test_sync_common_codes_script.py tests/test_schema_elections_master.py`
  - `../election2026_codex/.venv/bin/pytest -q`
  - `set -a; source /Users/gimtaehun/election2026_codex/.env; set +a; PYTHONPATH=. ../election2026_codex/.venv/bin/python scripts/sync_elections_master.py --dry-run --report-path data/elections_master_sync_report.json`
- 결과:
  - `7 passed`
  - `188 passed`
  - 드라이런 리포트 생성 성공

## 5. 수용 기준 대비
1. regions 전수에 대해 office_type 조합 누락 0
- 충족: `data/elections_master_sync_report.json`의 `missing_default_slot_pairs=0`.

2. elections sync 실행 후 poll 0건이어도 region별 슬롯 조회 가능
- 충족: `without_poll_data_slot_count=44`, `acceptance_checks.slots_queryable_even_without_poll=true`.

3. QA가 DB 카디널리티 검증 가능한 리포트 제공
- 충족: `data/elections_master_sync_report.json`에 지역수/슬롯수/기본쌍 누락/샘플 체크 포함.

4. 샘플 검증
- `26-710` 슬롯 수: `2` (기준 충족)
- 강원 샘플(`32-000` 또는 `42-000`)은 현재 로컬 마스터에 region row가 없어 `acceptance_meta.metro_sample_region_present=false`로 기록.
  - 기능 결함이 아닌 데이터셋 범위 이슈로 분리 표기.

## 6. 의사결정 필요사항
1. 강원 샘플 기준 코드 확정 필요
- 운영 기준이 `32-000`인지 `42-000`인지(또는 `KR-32` alias) 확정이 필요합니다.
- 확정 후 `sample_checks` 키를 단일 코드 기준으로 고정 가능합니다.

2. 재보궐 office_type 정규화 범위 확정 필요
- 현재는 `%재보궐%` 관측값을 그대로 슬롯에 추가합니다.
- 운영에서 canonical office_type 사전으로 축약/정규화할지 결정이 필요합니다.
