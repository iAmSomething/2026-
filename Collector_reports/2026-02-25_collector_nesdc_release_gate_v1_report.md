# 2026-02-25 Collector NESDC Release Gate v1 Report

## 1. 대상 이슈
- Issue: #262 `[COLLECTOR][S7] NESDC 공개시점 게이트 + PDF 어댑터 확장 v1`

## 2. 구현 내용
- 파일: `scripts/generate_nesdc_safe_collect_v1.py`
- 변경 핵심:
  - 공개시점 정책을 고정 48h에서 정책형 게이트로 변경
    - 일반 매체: 24h
    - 정기간행물: 48h
  - `release_at_kst` 계산 후 `now >= release_at_kst`일 때만 결과분석 파싱 시도
  - 비공개건은 `collect_status = pending_official_release`로 `pending_records`에 보존
  - 조사 메타(`legal_meta`)와 문항 결과(`result_options`)를 분리 저장
  - adapter profile 분기 정보 추가
    - `adapter_profile.profile_key` (`ntt:<id>` / `pollster:<기관명>`)
  - 정책/상태 지표 추가
    - `release_gate_applied_all`
    - `pending_nonpublic_state_preserved`
    - `recent20_policy_violation_zero`
    - `adapter_profile_counts`

## 3. 테스트
- 파일: `tests/test_nesdc_safe_collect_v1_script.py`
- 신규/갱신 검증:
  - explicit true + release_at 미도달 시 차단(`SAFE_WINDOW_GUARD_BLOCKED`)
  - 정기간행물 48h 정책 적용 및 pending 상태 유지
- 실행:
  - `pytest -q tests/test_nesdc_safe_collect_v1_script.py tests/test_nesdc_live_v1_pack_script.py`
- 결과:
  - `12 passed`

## 4. 산출물
- `data/collector_nesdc_safe_collect_v1.json`
- `data/collector_nesdc_safe_collect_v1_report.json`
- `data/collector_nesdc_safe_collect_v1_review_queue_candidates.json`
- `data/collector_nesdc_release_gate_v1_eval.json`

## 5. 실측 결과
1. 현재 시점 실행(`as_of=2026-02-26T07:33+09:00`)
- `recent20_release_policy_violation_count = 0`
- `release_gate_applied_all = true`
- `pending_nonpublic_state_preserved = true`

2. 조기 시점 실행(`as_of=2026-02-18T00:00+09:00`)
- `pending_official_release_count = 11`
- pending 샘플이 `collect_status=pending_official_release`로 유지됨(평가 파일 포함)

## 6. 완료 기준 매핑
1. 최근 등록건 샘플 20건에서 정책위반 수집 0건
- 충족 (`recent20_release_policy_violation_count = 0`)

2. 결과분석 비공개건은 pending_official_release 상태 유지
- 충족 (`collector_nesdc_release_gate_v1_eval.json`의 early run pending 샘플)

3. evidence 제출
- 충족 (산출물 4종 제출)

## 7. 리스크/후속
- 현재 데이터에서는 `pending_official_release_count`가 시점 의존적이므로, 운영 파이프라인에서는 실행시각 기준으로 pending 규모가 변동됨.
- 후속으로 `#261`(기사 법정필수항목 추출 엄밀화)과 결합 시, NESDC 메타를 기사 추출 보강 입력으로 사용해 completeness 개선 필요.
