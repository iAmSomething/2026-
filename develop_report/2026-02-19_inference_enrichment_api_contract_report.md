# 2026-02-19 Inference/Enrichment API Contract Report

## 1. 작업 목표
- Issue: #95 `[DEVELOP] 추정/보강 메타 API 계약 확장(date_inference/enriched/review)`
- 대상 API: `GET /api/v1/matchups/{matchup_id}`
- 목표: 아래 필드를 계약/조회/문서/샘플에 일관 반영
  - `date_inference_mode`
  - `date_inference_confidence`
  - `nesdc_enriched`
  - `needs_manual_review`

## 2. 구현 내용
1. API 응답 스키마 확장
- `app/models/schemas.py`
  - `MatchupOut`에 `nesdc_enriched: bool = False`
  - `MatchupOut`에 `needs_manual_review: bool = False`

2. 저장소 조회 로직 확장
- `app/services/repository.py` (`get_matchup`)
  - `nesdc_enriched` 계산:
    - `source_channel='nesdc'` 또는 `source_channels`에 `nesdc` 포함 시 `true`
  - `needs_manual_review` 계산:
    - `review_queue`에서 동일 `observation_key` 기준
    - `entity_type IN ('poll_observation', 'ingest_record')`
    - `status IN ('pending', 'in_progress')`
    - 존재 시 `true`

3. 계약 테스트 보강
- `tests/test_api_routes.py`
  - `matchup` 응답에 `nesdc_enriched`, `needs_manual_review` 검증 추가
- `tests/test_repository_matchup_legal_metadata.py`
  - repository 반환값에 `nesdc_enriched`, `needs_manual_review` 검증 추가

4. 문서 동기화
- `docs/03_UI_UX_SPEC.md`
  - 매치업 상세 필수 필드에 `nesdc_enriched`, `needs_manual_review` 반영
  - `needs_manual_review`의 `review_queue` 연계 규칙 명시

5. 샘플 응답 추가
- `data/inference_enrichment_matchup_sample_v1.json`
  - 확장 필드 포함 샘플 1건 추가

## 3. 검증 결과
1. 타겟 테스트
- 명령: `/Users/gimtaehun/election2026_codex/.venv/bin/pytest -q tests/test_repository_matchup_legal_metadata.py tests/test_api_routes.py`
- 결과: `7 passed`

2. 전체 테스트
- 명령: `/Users/gimtaehun/election2026_codex/.venv/bin/pytest -q`
- 결과: `67 passed`

## 4. DoD 점검
1. 계약 테스트 PASS: 완료
2. 샘플 응답 + 보고서 제출: 완료
3. 문서 필드 동기화: 완료

## 5. 산출물 경로
- `develop_report/2026-02-19_inference_enrichment_api_contract_report.md`
- `data/inference_enrichment_matchup_sample_v1.json`
