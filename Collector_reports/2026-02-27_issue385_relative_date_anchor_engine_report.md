# 2026-02-27 Issue #385 실행 보고서 (Collector)

## 1) 작업 개요
- 이슈: `#385` `[W6][COLLECTOR][P1] 기사 상대시점 날짜해석 엔진 고도화(게시일 anchor)`
- 목표:
  - 게시일 anchor 기준 상대시점 해석 정확도 개선
  - timezone/자정 경계 오차 축소
  - date inference 근거 payload 확장

## 2) 반영 내용
- `src/pipeline/collector.py`
  - 상대시점 룰셋 확장
    - 고정 신호: `그저께/그제/어제/오늘/지난주/이번주/최근`
    - 수치 신호: `N일 전`, `N주 전`, `N개월 전`, `지난 N일`, `지난달`
  - 게시일 anchor 해석 개선
    - `published_at`/`collected_at` 파싱 시 `Asia/Seoul` 기준 날짜 변환
    - UTC->KST 자정 경계(전일/당일 뒤틀림) 보정
  - 월 단위 이동 보강
    - `지난달`, `N개월 전`에서 월말 clamp 처리(예: 3/31 -> 2/28)
  - 증거 payload 확장
    - 상대시점 관련 review_queue payload에 아래 필드 추가:
      - `relative_signal`, `relative_offset_days`
      - `anchor_source`, `anchor_date`, `inferred_survey_end_date`
      - `published_at`, `collected_at`, `timezone`

- `tests/test_collector_extract.py`
  - 상대시점 경계/월단위/수치 표현 테스트 추가
  - strict_fail payload 확장 필드 검증 추가

## 3) 테스트 결과
- 실행 명령:
  - `../election2026_codex/.venv/bin/python -m pytest tests/test_collector_extract.py tests/test_contracts.py tests/test_collector_contract_freeze.py tests/test_ingest_adapter.py -q`
  - `../election2026_codex/.venv/bin/python -m pytest tests/test_collector_live_news_v1_pack_script.py tests/test_collector_live_coverage_v2_pack_script.py -q`
- 결과:
  - `31 passed`
  - `10 passed`

## 4) 증적 파일
- `data/issue385_relative_date_inference_evidence.json`

핵심 확인값:
- 총 7개 시나리오 검증, `passed_cases=7`
- KST 자정 경계 보정 케이스:
  - `published_at=2026-02-17T16:30:00+00:00` + `어제`
  - 결과 `survey_end_date=2026-02-17` (KST anchor 기준)
- 월말 clamp 케이스:
  - `published_at=2026-03-31T10:00:00+09:00` + `지난달`
  - 결과 `survey_end_date=2026-02-28`

## 5) 수용기준 대응
1. 상대시점 해석 정확도 개선
- 단순 키워드 기반에서 수치/월단위 패턴까지 확장했고, 7개 대표 시나리오 정확 매칭.

2. `date_inference_mode/confidence` 일관 저장
- 기존 모드 체계(`relative_published_at/estimated_timestamp/strict_fail_blocked`) 유지하면서 signal별 confidence를 일관 계산.

3. QA 날짜검증 PASS 준비
- 경계/패턴 케이스 테스트와 증빙 JSON 제출 완료. QA 측 재검증 입력으로 사용 가능.

## 6) 의사결정 요청
1. `이번주/최근` 신호의 confidence(현재 0.58/0.45)를 운영 임계치(0.8) 하회로 유지할지, 도메인별로 상향 조정할지 결정이 필요합니다.
2. 상대시점 해석 시 timezone을 `Asia/Seoul` 고정으로 두었는데, 해외 매체 확장 시 소스 timezone 우선 전략으로 전환할지 정책 결정이 필요합니다.
