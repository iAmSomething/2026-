# Collector 주간 품질 리포트 템플릿 (도메인 본문추출)

- 보고주차: YYYY-WW
- 작성일: YYYY-MM-DD
- 작성자: Collector

## 1. 주간 요약
1. 분석 대상 건수:
2. 전체 fetch_success_rate:
3. 전체 parse_success_rate:
4. 전체 extract_success_rate:

## 2. 정책별 성공률
1. direct_fetch:
2. blocklist_fallback:
3. fallback_after_fetch_error:
4. fetch_error:

## 3. 실패 상위 도메인 Top10
1. domain / failure_count / dominant_reason
2. ...

## 4. 개선 우선순위 Top5
1. domain / dominant_reason / action
2. ...

## 5. 이번 주 적용 개선안
1.
2.
3.

## 6. 다음 주 계획
1.
2.
3.

## 7. 산출물 경로
1. `data/collector_domain_extraction_quality_report.json`
2. `Collector_reports/YYYY-MM-DD_collector_domain_extraction_quality_report.md`
