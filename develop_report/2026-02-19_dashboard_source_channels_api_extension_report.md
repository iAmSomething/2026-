# 2026-02-19 Dashboard Source Channels API Extension Report (Issue #82)

## 1. 작업 개요
- 이슈: [#82](https://github.com/iAmSomething/2026-/issues/82)
- 목표: 대시보드 계열 API(`summary/map-latest/big-matches`)에 `source_channels`를 일관 노출
- 브랜치: `codex/issue82-dashboard-source-channels`

## 2. 구현 내용
### 2.1 API 응답 모델 확장
- 파일: `app/models/schemas.py`
- 확장 대상:
  - `SummaryPoint`
  - `MapLatestPoint`
  - `BigMatchPoint`
- 추가 필드:
  - `source_channel` (legacy 호환)
  - `source_channels` (`string[]`, 기본값 `[]`)

### 2.2 라우트/쿼리 반영
- 파일: `app/api/routes.py`
  - summary 응답 매핑 시 `source_channels` 누락/null을 `[]`로 보정
- 파일: `app/services/repository.py`
  - `fetch_dashboard_summary`
  - `fetch_dashboard_map_latest`
  - `fetch_dashboard_big_matches`
- SQL에서 `source_channels` fallback 규칙 반영:
  - `COALESCE(o.source_channels, CASE WHEN o.source_channel IS NULL THEN ARRAY[]::text[] ELSE ARRAY[o.source_channel] END)`

### 2.3 문서 동기화
- 파일: `docs/03_UI_UX_SPEC.md`
- 반영 항목:
  - 3개 대상 엔드포인트 필수 필드에 `source_channel`, `source_channels` 명시
  - null 정책: `source_channels`는 null 대신 `[]` 노출

### 2.4 UIUX 소비용 샘플 응답
- 파일: `data/dashboard_source_channels_samples_v1.json`
- 포함 내용:
  - `dashboard_summary`, `dashboard_map_latest`, `dashboard_big_matches` 예시
  - null/empty array 정책 명시

## 3. 테스트/검증
### 3.1 계약 테스트
- 파일: `tests/test_api_routes.py`
- 검증 항목:
  - `GET /api/v1/dashboard/summary`
  - `GET /api/v1/dashboard/map-latest`
  - `GET /api/v1/dashboard/big-matches`
  - 각 응답에서 `source_channels` 필드 존재 및 배열 형태 확인

### 3.2 실행 결과
- `/Users/gimtaehun/election2026_codex/.venv/bin/pytest -q tests/test_api_routes.py tests/test_repository_dashboard_summary_scope.py tests/test_poll_fingerprint.py tests/test_repository_source_channels.py`
  - 결과: `13 passed`
- `/Users/gimtaehun/election2026_codex/.venv/bin/pytest -q`
  - 결과: `61 passed`

## 4. DoD 충족 여부
1. 3개 엔드포인트 계약 테스트 PASS: 완료
2. 문서 필드 동기화: 완료 (`docs/03_UI_UX_SPEC.md`)
3. 보고서 + 샘플 응답 첨부: 완료
