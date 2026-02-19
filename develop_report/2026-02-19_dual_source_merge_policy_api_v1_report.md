# 2026-02-19 Dual Source Merge Policy API v1 Report

## 1. 작업 목표
- Issue: #113 `[DEVELOP] 기사+NESDC 이중소스 병합정책 API v1(source_priority/freshness)`
- 목표:
  1. 이중소스 병합 정책을 API에서 명시적으로 노출
  2. `summary/map/matchup` 응답 계약 동기화
  3. 스코프 오염/병합 충돌 회귀 보장

## 2. 구현 내용
1. API 계약 확장 (`app/models/schemas.py`)
- `summary/map/matchup`에 신규 필드 반영
  - `source_priority` (`official|article|mixed`)
  - `official_release_at`
  - `article_published_at`
  - `freshness_hours`
  - `is_official_confirmed`

2. source meta 파생 로직 (`app/api/routes.py`)
- 공통 함수 `_derive_source_meta()` 추가
- 산출 규칙:
  - `source_priority`
    - `mixed`: `source_channels`에 `article`+`nesdc` 동시 존재
    - `official`: `nesdc`만 존재
    - `article`: 그 외
  - `is_official_confirmed`: `nesdc` 포함 여부
  - `official_release_at`: 공식소스 존재 시 관측치 `updated_at` 기준
  - `article_published_at`: `articles.published_at`
  - `freshness_hours`: `official_release_at` 우선, 없으면 `article_published_at`, 없으면 `observation_updated_at`

3. repository 조회 보강 (`app/services/repository.py`)
- `summary/map/matchup` 조회에 `observation_updated_at`, `article_published_at` 추가
- `summary`는 기존 스코프 정책 유지(`audience_scope='national'` only)

4. 문서 동기화
- `docs/02_DATA_MODEL_AND_NORMALIZATION.md`: dual-source 파생필드 규칙 추가
- `docs/03_UI_UX_SPEC.md`: summary/map/matchup 필드 표 및 규칙 반영
- `docs/05_RUNBOOK_AND_OPERATIONS.md`: freshness/source_priority 운영 체크 추가

5. 샘플 응답
- `data/dual_source_merge_policy_samples_v1.json`

## 3. 회귀/계약 테스트
1. 타깃 테스트
- 명령:
  - `/Users/gimtaehun/election2026_codex/.venv/bin/pytest -q tests/test_api_routes.py tests/test_repository_dashboard_summary_scope.py tests/test_repository_matchup_legal_metadata.py tests/test_poll_fingerprint.py`
- 결과: `12 passed`

2. 전체 테스트
- 명령:
  - `/Users/gimtaehun/election2026_codex/.venv/bin/pytest -q`
- 결과: `69 passed`

## 4. 수용 기준 점검
1. 계약 테스트 PASS: 완료
2. 병합 우선순위/충돌 회귀 PASS: 완료
- `tests/test_api_routes.py`에서 `source_priority`/`is_official_confirmed`/`freshness_hours` 검증
- `tests/test_poll_fingerprint.py`의 충돌 검증 유지
3. 기존 endpoint 호환성 회귀 PASS: 완료 (전체 테스트 통과)

## 5. 산출물
- `develop_report/2026-02-19_dual_source_merge_policy_api_v1_report.md`
- `data/dual_source_merge_policy_samples_v1.json`
