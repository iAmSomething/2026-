# 2026-02-20 Issue #158 Dashboard Quality API 구현 보고서

## 1. 개요
- 이슈: `#158 [DEVELOP] 운영 품질 API 추가(/api/v1/dashboard/quality) + 공개 웹 연동 준비`
- 목표: 운영 품질 요약 지표를 API로 제공하고, null-safe 계약/문서/검증 산출물을 함께 제공

## 2. 구현 내용
1. 신규 공개 API 추가
- `GET /api/v1/dashboard/quality`
- 응답 필드
  - `generated_at`
  - `freshness_p50_hours`
  - `freshness_p90_hours`
  - `official_confirmed_ratio`
  - `needs_manual_review_count`
  - `source_channel_mix.article_ratio`
  - `source_channel_mix.nesdc_ratio`

2. 집계 로직
- `app/services/repository.py`에 `fetch_dashboard_quality()` 추가
- 기준 테이블: `poll_observations`, `articles`, `review_queue`
- freshness 계산 기준: `official_release_at` > `article_published_at` > `updated_at`
- ratio 계산 기준:
  - `official_confirmed_ratio`: `nesdc` 포함 관측치 비율
  - `source_channel_mix`: article/nesdc 포함 비율

3. 안정성(null-safe)
- 관측치 0건일 때
  - `freshness_p50_hours`, `freshness_p90_hours`: `null`
  - ratio/count 필드: `0` 반환
- `review_queue` 미존재/빈 결과에서도 500 없이 안전 응답

4. OpenAPI/Swagger 반영
- `DashboardQualityOut`, `SourceChannelMixOut` 스키마 추가
- 라우트 `response_model`로 자동 OpenAPI 노출

## 3. 변경 파일
- `app/models/schemas.py`
- `app/api/routes.py`
- `app/services/repository.py`
- `tests/test_api_routes.py`
- `docs/02_DATA_MODEL_AND_NORMALIZATION.md`
- `docs/03_UI_UX_SPEC.md`
- `docs/05_RUNBOOK_AND_OPERATIONS.md`

## 4. 검증 결과
1. 단위/계약 테스트
- 실행: `.venv313/bin/python -m pytest tests/test_api_routes.py -q`
- 결과: `9 passed`

2. curl 검증
- 로컬 서버: `uvicorn app.main:app --host 127.0.0.1 --port 8110`
- 호출: `GET http://127.0.0.1:8110/api/v1/dashboard/quality`
- 결과: HTTP `200`
- 로그: `data/verification/issue158_dashboard_quality_curl.log`

3. 샘플 응답 JSON
- 파일: `data/verification/issue158_dashboard_quality_sample.json`
- 예시 핵심값
  - `freshness_p50_hours: 93.6`
  - `freshness_p90_hours: 216.0`
  - `official_confirmed_ratio: 0.0`
  - `needs_manual_review_count: 1`

## 5. 수용기준 대응
1. `/api/v1/dashboard/quality` 200: 충족
2. null-safe + 타입 일관성: 충족(테스트 포함)
3. QA 계약 테스트 가능 명세: 충족(스키마 + docs 동기화)
