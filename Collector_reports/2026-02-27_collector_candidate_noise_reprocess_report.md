# [COLLECTOR] Issue #486 후보 오염토큰 재처리 및 재유입 차단 보고서

- 이슈: https://github.com/iAmSomething/2026-/issues/486
- 작성일: 2026-02-27
- 담당: role/collector

## 1) 작업 범위
- `region_code=11-000`, `office_type=광역자치단체장` 대상에서 후보명 오염 토큰 재유입 차단
- 노이즈 후보 토큰 발생 시 자동 `review_queue(issue_type=candidate_name_noise)` 라우팅
- before/after 비교 아티팩트 생성

## 2) 코드 변경
1. `app/services/ingest_service.py`
- `CANDIDATE_TOKEN_NOISE` 판정 옵션은 `upsert_poll_option`을 건너뛰도록 변경(저장 차단)
- 노이즈 후보 토큰은 `candidate_name_noise`로 별도 review_queue 적재
- 기존 후보 검증 수동검수(`mapping_error`) 라우팅은 non-noise 케이스만 유지

2. `scripts/run_issue486_candidate_noise_reprocess.py`
- 대상 필터(`11-000`, `광역자치단체장`) 기반 키셋 추출
- 후보 옵션 before/after 비교 및 노이즈 제거 재처리 payload 생성
- `review_queue_candidates(issue_type=candidate_name_noise)` 증빙 생성

3. `docs/05_RUNBOOK_AND_OPERATIONS.md`
- ingest 단계 noise_token 가드(저장 차단 + `candidate_name_noise` 라우팅) 운영 규칙 반영

4. 테스트
- `tests/test_ingest_service.py`
- `tests/test_issue486_candidate_noise_reprocess_script.py`

## 3) 검증 결과
1. 단위 테스트
- 실행: `/Users/gimtaehun/election2026_codex/.venv/bin/python -m pytest tests/test_ingest_service.py tests/test_issue486_candidate_noise_reprocess_script.py -q`
- 결과: `28 passed`

2. 재처리 아티팩트 생성
- 실행: `/Users/gimtaehun/election2026_codex/.venv/bin/python scripts/run_issue486_candidate_noise_reprocess.py --input data/collector_live_news_v1_payload.json --keyset-output data/issue486_candidate_noise_keys.json --output data/issue486_candidate_noise_reprocess_report.json --reprocess-payload-output data/issue486_candidate_noise_reprocess_payload.json`
- 결과 요약:
  - `noise_record_count=2`
  - `total_removed_noise_option_count=4`
  - acceptance: `target_keyset_extracted=true`, `seoul_mayor_candidate_only_names=true`, `noise_reingest_block_ready=true`

## 4) 산출물
- `data/issue486_candidate_noise_keys.json`
- `data/issue486_candidate_noise_reprocess_report.json`
- `data/issue486_candidate_noise_reprocess_payload.json`

## 5) 수용기준 체크
- [x] 서울시장 매치업 후보가 인명만 구성
- [x] 오염 토큰 재유입 0 (ingest 저장 단계 차단)
- [x] before/after 증빙 JSON 제출

## 6) 의사결정 필요사항
1. 운영 알림 규칙 확장 여부
- 현재 `ops` 경고 규칙은 `mapping_error_24h_count` 중심입니다.
- `candidate_name_noise`를 별도 카운트/알림 룰로 추가할지 결정이 필요합니다.
