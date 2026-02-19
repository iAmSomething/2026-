# 2026-02-19 Fingerprint Merge Policy v1 Report (Issue #75)

## 1. 작업 개요
- 이슈: [#75](https://github.com/iAmSomething/2026-/issues/75)
- 목표: 기사/NESDC 혼합 입력에서 동일 조사 중복을 `poll_fingerprint` 기준으로 제어
- 브랜치: `codex/issue75-poll-fingerprint-merge`

## 2. 구현 사항
### 2.1 fingerprint 규칙 구현
- 파일: `app/services/fingerprint.py`
- 입력 필드: `pollster`, `sponsor`, `survey_start_date`, `survey_end_date`, `region_code(or region_text)`, `sample_size`, `method`
- 정규화 후 `sha256` 해시로 `poll_fingerprint` 생성

### 2.2 스키마/적재 경로 반영
- 파일: `db/schema.sql`
- `poll_observations` 신규 컬럼:
  - `sponsor`, `method`
  - `poll_fingerprint`, `source_channel(article|nesdc)`
- 체크 제약:
  - `poll_observations_source_channel_check`
- 인덱스:
  - `idx_poll_observations_fingerprint`

- 파일: `app/models/schemas.py`
  - `PollObservationInput`에 `sponsor`, `method`, `poll_fingerprint`, `source_channel` 추가
  - `MatchupOut`에 `poll_fingerprint`, `source_channel` 노출

- 파일: `app/services/ingest_service.py`
  - observation 입력에 fingerprint 누락 시 자동 생성
  - `DuplicateConflictError` 발생 시 review_queue `issue_type='DUPLICATE_CONFLICT'`로 분기

- 파일: `app/services/repository.py`
  - fingerprint 사전 조회 후 병합 정책 적용
  - 동일 fingerprint 다중 소스 병합 시 정책:
    - 메타: `nesdc` 우선
    - 문맥(`survey_name`): `article` 우선 보강

### 2.3 충돌 분기 정책
- 파일: `app/services/fingerprint.py`
- 동일 fingerprint라도 핵심 식별 필드(`region_code`, `office_type`, `survey_start_date`, `survey_end_date`, `sample_size`) 불일치 시
  - `DuplicateConflictError` 발생
  - ingest에서 `review_queue`로 `DUPLICATE_CONFLICT` 기록

### 2.4 문서/산출물
- 문서 반영:
  - `docs/02_DATA_MODEL_AND_NORMALIZATION.md`
  - `docs/03_UI_UX_SPEC.md`
- 검증 산출물:
  - `data/fingerprint_merge_validation_v1.json`

## 3. 테스트/검증
### 3.1 신규/수정 테스트
- 신규: `tests/test_poll_fingerprint.py`
  - fingerprint 정규화 안정성
  - NESDC 우선 + 기사 문맥 보강 병합 정책
  - 핵심 필드 충돌 시 `DuplicateConflictError`
- 수정:
  - `tests/test_ingest_service.py`
  - `tests/test_api_routes.py`
  - `tests/test_ingest_adapter.py`

### 3.2 실행 결과
- `/Users/gimtaehun/election2026_codex/.venv/bin/pytest -q tests/test_poll_fingerprint.py tests/test_ingest_service.py tests/test_api_routes.py tests/test_ingest_adapter.py tests/test_repository_dashboard_summary_scope.py`
  - 결과: `15 passed`
- `/Users/gimtaehun/election2026_codex/.venv/bin/pytest -q`
  - 결과: `59 passed`

## 4. DoD 충족 여부
1. fingerprint 생성/저장/조회 경로 동작: 완료
2. 혼합 입력 2회 적재 시 중복 증가 0: 완료(정책 검증 + 산출물 반영)
3. 충돌 분기(review_queue) 동작 확인: 완료(`DUPLICATE_CONFLICT`)
4. 관련 테스트 + 전체 테스트 PASS: 완료

## 5. 의사결정 필요사항
1. `source_channel` 최종 표현 정책
- 현재: 단일 값(`article|nesdc`)만 저장, 병합 후에는 `nesdc`가 존재하면 `nesdc`로 수렴
- 선택지:
  - A) 현행 유지(단순/빠름)
  - B) 다중 provenance(`article+nesdc`) 별도 필드로 확장(추적성 강화)
