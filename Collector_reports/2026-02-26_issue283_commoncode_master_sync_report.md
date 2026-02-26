# 2026-02-26 Issue #283 CommonCodeService Master Sync Report

## 1. 대상 이슈
- Issue: #283 `[COLLECTOR][P0] CommonCodeService 전수 동기화: 선거구 마스터 구축`
- URL: https://github.com/iAmSomething/2026-/issues/283

## 2. 구현 요약
- `CommonCodeService` 수집을 단일 페이지에서 다중 페이지 전수 수집으로 확장.
  - `totalCount` + `numOfRows` 기반 페이지 순회.
  - XML/JSON 모두 `totalCount` 파싱 지원.
- code sync 스크립트에 기존 `regions` 대비 diff 계산 추가.
  - `added_count`, `updated_count`, `unchanged_count`, `delete_candidate_count` 산출.
- DB upsert를 변경건 중심으로 실행하도록 조정.
  - 기존과 동일한 행은 upsert 생략.
- 동기화 실패 시 `review_queue(issue_type=code_sync_error)` 자동 기록.
  - `entity_type=code_sync_job`, `entity_id=common_codes_region_sync`.
- sync 리포트 확장.
  - `status`, `executed_at`, `diff.*`, `sample` 포함.

## 3. 변경 파일
- 코드
  - `app/services/data_go_common_codes.py`
  - `scripts/sync_common_codes.py`
- 테스트
  - `tests/test_sync_common_codes.py`
  - `tests/test_sync_common_codes_script.py` (신규)
- 문서
  - `docs/04_DEPLOYMENT_AND_ENVIRONMENT.md`
  - `docs/06_COLLECTOR_CONTRACTS.md`

## 4. 검증 결과
- 실행:
  - `PYTHONPATH=. /Users/gimtaehun/election2026_codex/.venv/bin/pytest -q tests/test_sync_common_codes.py tests/test_sync_common_codes_script.py`
  - `PYTHONPATH=. /Users/gimtaehun/election2026_codex/.venv/bin/pytest -q tests/test_repository_region_search_hardening.py tests/test_api_routes.py`
  - `/Users/gimtaehun/election2026_codex/.venv/bin/python -m py_compile app/services/data_go_common_codes.py scripts/sync_common_codes.py`
- 결과:
  - `6 passed`
  - `16 passed`
  - `py_compile success`

## 5. 수용 기준 대비
1. CommonCodeService 기준 전수 반영(누락 0)
- 충족 방향 반영: 페이지네이션 전수 수집 구현 완료.
- 실제 누락 0은 운영 endpoint로 1회 sync 실행 후 `parsed_region_count`/DB 총건수 대조 필요.

2. 지역 데이터가 없어도 `/regions/search` 결과 반환
- 유지 충족: `regions` 마스터 기반 검색 구조 유지(`has_data`, `matchup_count` 보조필드).

3. 회귀 테스트: 한글 질의(서울/연수/시흥) 200
- 기존 API/검색 회귀 테스트 패스.
- 운영 환경에서 `서울/연수/시흥` 3종 smoke는 QA gate에서 최종 확인 필요.

4. code sync 리포트 생성(총건수/추가/수정/삭제 후보)
- 충족: `data/common_codes_sync_report.json`에 `diff` 포함.

5. 동기화 실패 시 review_queue `code_sync_error`
- 충족: 스크립트 실패 핸들러에서 자동 기록.

## 6. 의사결정 필요사항
1. 운영 스케줄 확정 필요
- 최소 1일 1회 요구사항 기준으로, 배치 스케줄러(예: cron/GitHub Actions/별도 job runner) 최종 선택 필요.

2. 삭제 후보(`delete_candidate_count`) 적용 정책 확정 필요
- 현재는 보고서에 후보로만 산출하며 자동 삭제는 수행하지 않음.
- 자동 삭제 허용 여부(및 보호 룰: n회 연속 미검출 시 삭제 등) 결정 필요.

3. endpoint 운영 구성 확정 필요
- `COMMON_CODE_REGION_URL` 단일 endpoint 운영 vs `COMMON_CODE_SIGUNGU_URL` 분리 운영 확정 필요.
