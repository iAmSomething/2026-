# 2026-02-27 Issue #388 공개 API 계약 v2 정리 보고서

## 1. 작업 개요
- 이슈: #388 `[W5][DEVELOP][P1] 공개 API 계약 v2 정리(canonical/article/source_trace)`
- 목표: 대시보드/매치업 계약을 v2로 정렬하고, 프론트 fallback 분기를 줄일 수 있도록 표준 필드(`canonical_title`, `article_title`, `source_trace`)를 도입

## 2. 구현 내용
### 2.1 스키마 계약 정리
- `app/models/schemas.py`
- 신규 공통 메타 모델 추가:
  - `SourceTraceOut`
    - `source_priority`
    - `source_channel`
    - `source_channels`
    - `selected_source_tier`
    - `selected_source_channel`
    - `official_release_at`
    - `article_published_at`
    - `freshness_hours`
    - `is_official_confirmed`
- 적용 대상:
  - `SummaryPoint.source_trace`
  - `MapLatestPoint.source_trace`
  - `BigMatchPoint.source_trace`
  - `MatchupOut.source_trace`
- 제목 계약 v2 적용:
  - `MapLatestPoint`: `canonical_title`, `article_title` 추가
  - `BigMatchPoint`: `canonical_title`, `article_title` 추가
  - `MatchupOut`: 기존 `canonical_title`, `article_title` 유지
- 하위호환(deprecated) 명시:
  - `title`
  - `source_priority`
  - `source_channel`
  - `source_channels`
  - `official_release_at`
  - `article_published_at`
  - `freshness_hours`
  - `is_official_confirmed`
  - (summary 전용) `selected_source_tier`, `selected_source_channel`

### 2.2 라우트 응답 매핑 통일
- `app/api/routes.py`
- 공통 헬퍼 추가:
  - `_build_source_trace(...)`
  - `_normalize_title_fields(...)`
- 적용:
  - `GET /api/v1/dashboard/summary`
    - 포인트별 `source_trace` 구성
    - 대표값 선택 결과(`selected_source_tier`, `selected_source_channel`)를 `source_trace`에도 반영
  - `GET /api/v1/dashboard/map-latest`
    - `canonical_title/article_title/title(deprecated)` 정규화
    - `source_trace` 구성
  - `GET /api/v1/dashboard/big-matches`
    - `canonical_title/article_title/title(deprecated)` 정규화
    - `source_trace` 구성
  - `GET /api/v1/matchups/{matchup_id}`
    - 제목 필드 정규화(`canonical_title/article_title/title`)
    - `source_trace` 구성

### 2.3 Repository 응답 확장
- `app/services/repository.py`
- `fetch_dashboard_map_latest`:
  - `article_title`(기사 제목) 조회
  - `canonical_title`(정규 제목) 조회
- `fetch_dashboard_big_matches`:
  - `article_title`(기사 제목) 조회
  - `canonical_title`(정규 제목) 조회

### 2.4 계약 테스트 보강
- `tests/test_api_routes.py`
- 검증 추가:
  - summary/map/big/matchup 응답에 `source_trace` 존재 및 값 정합성
  - map/big/matchup의 `canonical_title/article_title` 계약
  - summary 대표값 선택 시 `source_trace.selected_source_tier` 정합성

### 2.5 문서 업데이트
- `docs/02_DATA_MODEL_AND_NORMALIZATION.md`
  - 공통 메타 `source_trace`와 제목 계약 v2 규칙 추가
  - deprecated 유지 규칙 명시
- `docs/03_UI_UX_SPEC.md`
  - 화면-데이터 매핑을 `source_trace` 중심으로 갱신
  - `canonical_title/article_title` 도입 및 deprecated 필드 명시

## 3. 검증 결과
- 실행 1:
  - `/Users/gimtaehun/election2026_codex/.venv/bin/pytest -q tests/test_api_routes.py`
  - 결과: `31 passed`
- 실행 2:
  - `/Users/gimtaehun/election2026_codex/.venv/bin/pytest -q tests/test_repository_matchup_legal_metadata.py tests/test_map_latest_cleanup_policy.py`
  - 결과: `3 passed`

## 4. 수용기준 대응
1. 필드 불일치 0
- 대시보드/매치업 표준 필드(`canonical_title`, `article_title`, `source_trace`)를 스키마/라우트/테스트/문서에 동기 반영

2. 프론트 fallback 분기 축소
- 제목과 출처 메타를 단일 구조로 제공하여 분기 기준을 단순화

3. QA 계약검증 PASS
- 계약 테스트(라우트 + 관련 리포지토리 회귀) 통과

## 5. 변경 파일
- `app/models/schemas.py`
- `app/api/routes.py`
- `app/services/repository.py`
- `tests/test_api_routes.py`
- `docs/02_DATA_MODEL_AND_NORMALIZATION.md`
- `docs/03_UI_UX_SPEC.md`
