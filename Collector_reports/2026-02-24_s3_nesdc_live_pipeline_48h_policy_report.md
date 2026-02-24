# [COLLECTOR][S3] NESDC 실데이터 파이프라인 편입(48h 정책 준수) 보고서 (#228)

## 1) 목표
- NESDC 등록현황을 실데이터 소스로 정식 편입
- 48시간 안전윈도우(정기간행물 48h 포함) 필터 준수
- 기관별 PDF 파싱 어댑터 실패 시 review_queue 라우팅
- 실데이터 파싱 성공 20건 이상 증빙
- 기사 소스와 중복/충돌 시 merge 정책 적용 증빙

## 2) 구현 내용
1. NESDC live pack 스크립트 추가/고도화
- `scripts/generate_nesdc_live_v1_pack.py`
- `generate_nesdc_safe_collect_v1` 결과를 상위 팩으로 통합
- 기사 소스(`data/collector_live_news_v1_payload.json`)와 pollster/date/sample/margin 지문으로 중복/충돌 판정
- merge decision:
  - `insert_new`: 기사 소스 중복 없음
  - `merge_exact`: 핵심 지문 일치
  - `conflict_review`: 중복 후보 존재 + 핵심 지문 불일치 -> `review_queue(issue_type=mapping_error)`
- 실데이터 문자열 변형 대응 보강:
  - 표본수 숫자 파서 추가(`1,000명` 등)
  - 오차범위 파서 보강(`95% 신뢰수준 ±3.1%p`에서 ±값 우선)

2. 테스트 추가
- `tests/test_nesdc_live_v1_pack_script.py`
- 검증 항목:
  - merge 정책 3분기(`merge_exact/conflict_review/insert_new`)
  - 충돌 건 review_queue 라우팅
  - `parse_success_ge_20` acceptance threshold

## 3) 산출물
- `data/nesdc_live_v1.json`
- `data/nesdc_live_v1_report.json`
- `data/nesdc_live_v1_review_queue_candidates.json`
- `data/nesdc_live_v1_merge_policy_evidence.json`

## 4) 검증
### 4-1. 테스트
```bash
PYTHONPATH=. /Users/gimtaehun/election2026_codex/.venv/bin/pytest -q \
  tests/test_nesdc_live_v1_pack_script.py \
  tests/test_nesdc_safe_collect_v1_script.py \
  tests/test_collector_extract.py
```
- 결과: `17 passed`

### 4-2. 실데이터 배치 생성
```bash
PYTHONPATH=. /Users/gimtaehun/election2026_codex/.venv/bin/python \
  scripts/generate_nesdc_live_v1_pack.py
```

리포트 핵심 수치(`data/nesdc_live_v1_report.json`):
- nesdc_record_count: `92`
- safe_window_eligible_count: `92`
- parse_success_count: `34`
- review_queue_candidate_count: `92`
- acceptance:
  - `parse_success_ge_20=true`
  - `safe_window_policy_applied=true`
  - `adapter_failure_review_queue_present=true`
  - `article_merge_policy_evidence_present=true`

merge 정책 증빙(`data/nesdc_live_v1_merge_policy_evidence.json`):
- decision_counts:
  - `insert_new=89`
  - `conflict_review=3`
- review_queue issue_type 분포(`data/nesdc_live_v1_review_queue_candidates.json`):
  - `mapping_error=34`
  - `extract_error=58`

## 5) 완료 기준 충족 여부
- `data/nesdc_live_*` 산출물 + 보고서 제출: 충족
- 48h 정책 필터 적용: 충족
- 어댑터 실패 시 review_queue 라우팅: 충족
- 실데이터 파싱 성공 20건 이상: 충족(`34`)
- 기사 소스 중복/충돌 merge 정책 증빙: 충족

## 6) 의사결정 필요사항
1. 현재 기사 소스와 NESDC 간 `merge_exact`가 0건입니다.
- 지문 기준을 유지할지, 허용 오차(날짜/표본수/오차범위 일부 불일치 허용)를 둘지 결정 필요.
2. review_queue 후보가 92건으로 높습니다.
- `extract_error` 우선 해소(기관 템플릿 확장)와 `mapping_error` triage 우선순위 정책 결정 필요.
