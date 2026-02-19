# 2026-02-19 Provenance Multi Source Model v1 Report (Issue #78)

## 1. 작업 개요
- 이슈: [#78](https://github.com/iAmSomething/2026-/issues/78)
- 목표: 하위호환을 유지한 채 다중 provenance(`source_channels`) 도입
- 브랜치: `codex/issue78-provenance-multi-source`

## 2. 구현 내용
### 2.1 데이터 모델 확장
- 파일: `db/schema.sql`
- `poll_observations`에 `source_channels TEXT[]` 추가
- 기존 `source_channel` 유지(하위호환)
- 제약/인덱스:
  - `poll_observations_source_channels_check`
  - `idx_poll_observations_source_channels` (GIN)
- 백필 규칙 반영:
  - `source_channels IS NULL AND source_channel IS NOT NULL`인 기존 레코드에 대해 `source_channels = ARRAY[source_channel]`

### 2.2 병합 정책 확장
- 파일: `app/services/fingerprint.py`
- 병합 시 provenance 집합 누적:
  - 기존 `source_channels` + 신규 `source_channels` + 단일 `source_channel` 값을 모두 합쳐 dedupe
  - 정렬된 결과(`article`, `nesdc`)를 `source_channels`에 저장
- 단일 필드 호환 유지:
  - `source_channel`은 기존 규칙 유지(`nesdc` 포함 시 `nesdc`)

### 2.3 적재/조회 경로 반영
- 파일: `app/services/repository.py`
  - payload 준비 시 `source_channels` 누락이면 `[source_channel]`로 자동 보강
  - upsert에 `source_channels` 반영
  - `GET /api/v1/matchups/{matchup_id}` 조회에 `source_channels` 노출
- 파일: `app/models/schemas.py`
  - `PollObservationInput`, `MatchupOut`에 `source_channels` 추가
- 파일: `src/pipeline/contracts.py`, `src/pipeline/ingest_adapter.py`, `src/pipeline/collector.py`
  - contracts/adapter/collector 전파 경로에 `source_channels` 반영

### 2.4 문서/산출물
- 문서 반영:
  - `docs/02_DATA_MODEL_AND_NORMALIZATION.md`
  - `docs/03_UI_UX_SPEC.md`
- 검증 산출물:
  - `data/provenance_migration_validation_v1.json`

## 3. 테스트/검증
### 3.1 신규/수정 테스트
- 신규: `tests/test_repository_source_channels.py`
  - payload 백필(`source_channels=[source_channel]`) 검증
- 수정: `tests/test_poll_fingerprint.py`
  - 병합 후 `source_channels=[article, nesdc]` 누적 검증
- 수정: API/ingest/adapter 테스트
  - `source_channels` 계약 노출/전파 검증

### 3.2 실행 결과
- `/Users/gimtaehun/election2026_codex/.venv/bin/pytest -q tests/test_poll_fingerprint.py tests/test_repository_source_channels.py tests/test_ingest_service.py tests/test_api_routes.py tests/test_ingest_adapter.py tests/test_repository_dashboard_summary_scope.py`
  - 결과: `17 passed`
- `/Users/gimtaehun/election2026_codex/.venv/bin/pytest -q`
  - 결과: `61 passed`

## 4. DoD 충족 여부
1. 하위호환 깨짐 0건: 완료(`source_channel` 유지)
2. provenance 병합 정확성 테스트 PASS: 완료
3. 계약/회귀 테스트 PASS: 완료

## 5. 의사결정 필요사항
1. `source_channels` 노출 순서 정책 고정 여부
- 현재: `article`, `nesdc` 순서로 정규화
- 필요 시 UI 요구에 맞춰 우선순위(예: `nesdc` first) 재정의 가능
