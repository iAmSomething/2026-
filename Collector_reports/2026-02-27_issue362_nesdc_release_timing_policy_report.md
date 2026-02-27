# 2026-02-27 Issue #362 실행 보고서 (Collector)

## 1) 작업 개요
- 이슈: `#362` `[W1][COLLECTOR][P1] NESDC 24/48h 공개정책 기반 수집 타이밍 고도화`
- 목표:
  - 공개시점 정책 위반 조기 수집 시도 제거
  - 공개시점 기반 대기/재시도 계약(2h/6h/24h) 고정
  - 실패 사유 코드 `release_not_open`, `pdf_pending` 반영

## 2) 반영 내용
- `scripts/generate_nesdc_safe_collect_v1.py`
  - 공개시점 계산 필드 `earliest_release_at_kst`를 `records/pending_records`에 공통 반영
  - 공개 전 수집 차단 시 `pending_reason_code=release_not_open` 저장
  - 재시도 정책 상수 `RETRY_SCHEDULE_HOURS=(2,6,24)` 추가
  - `retry_plan`, `next_retry_at_kst`를 pending/fallback 레코드에 반영
  - PDF 미파싱 fallback 경로를 `pending_reason_code=pdf_pending`으로 통일
  - review_queue `error_code`를 `pdf_pending`으로 반영
  - 운영 리포트에 `pending_reason_counts`, `recollect_within_plus2h`, `retry_schedule_hours` 추가
- `tests/test_nesdc_safe_collect_v1_script.py`
  - 정기간행물 48h 경계 테스트에 reason/retry 검증 추가
  - adapter 누락 fallback 시 `pdf_pending` 라우팅 테스트 추가

## 3) 검증 결과
- 실행 명령:
  - `../election2026_codex/.venv/bin/python -m pytest tests/test_nesdc_safe_collect_v1_script.py -q`
- 결과:
  - `8 passed`

## 4) 증적 파일
- 운영 산출물 갱신:
  - `data/collector_nesdc_safe_collect_v1.json`
  - `data/collector_nesdc_safe_collect_v1_report.json`
  - `data/collector_nesdc_safe_collect_v1_review_queue_candidates.json`
- 이슈 증빙:
  - `data/issue362_nesdc_release_policy_sample5.json`
  - `data/issue362_plus2h_success_probe.json`

핵심 확인값:
- 24h/48h 혼합 샘플 5건: `release_policy_hours=[48,24,24,24,24]`
- 공개 전 대기 건: `ntt_id=17417`, `collect_status=pending_official_release`, `pending_reason_code=release_not_open`
- 동일 건 공개 후 재수집: `ntt_id=17417`, `collect_status=collected_template_fallback`
- `+2h` 지표(pre probe): `success_rate=0.8571 (6/7)`
- `+2h` 지표(post probe): `success_rate=1.0 (1/1)`

## 5) 수용기준 대응
1. premature fetch 0건
- 공개 전 건은 `pending_official_release`로만 남고, result option 추출/수집으로 진입하지 않음을 확인.

2. 공개 시점 +2h 내 재수집 성공률 리포트 제출
- `data/issue362_plus2h_success_probe.json`에 pre/post probe 및 동일 ntt 전이 증빙 포함.

3. 관련 테스트 PASS
- `tests/test_nesdc_safe_collect_v1_script.py` 전체 PASS 확인.

## 6) 의사결정 요청
1. `pdf_pending`을 review_queue `issue_type=extract_error`로 유지할지, `fetch_error`로 분리할지 정책 확정이 필요합니다.
2. `retry_schedule_hours=(2,6,24)`를 고정 상수로 유지할지, 운영 설정값으로 외부화할지 결정이 필요합니다.
