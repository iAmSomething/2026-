# 수집기 도메인별 본문추출 성공률 리포트 및 개선 우선순위

- 보고일: 2026-02-19
- 작성자: Codex (Collector 담당)
- 대상 이슈: `#36` `[COLLECTOR] 도메인별 본문추출 성공률 리포트 + 개선 우선순위`

## 1. 완료 요약
1. 도메인별 fetch/parse/extract 성공률 집계 스크립트 추가 완료
2. 실패 상위 도메인 Top10 및 원인 분류 자동화 완료
3. robots/fetch 정책별 성공률 비교 지표 생성 완료
4. 주간 품질 리포트 템플릿 생성 완료

## 2. 구현 산출물
1. 스크립트: `scripts/analyze_domain_extraction_quality.py`
2. 리포트 데이터: `data/collector_domain_extraction_quality_report.json`
3. 주간 템플릿: `Collector_reports/collector_weekly_domain_quality_template.md`
4. 테스트: `tests/test_domain_extraction_quality_script.py`

## 3. 실행/검증
### 3.1 실행 명령
```bash
PYTHONPATH=. .venv/bin/python scripts/analyze_domain_extraction_quality.py
```

### 3.2 테스트
1. `PYTHONPATH=. .venv/bin/python -m pytest -q tests/test_domain_extraction_quality_script.py tests/test_collector_extract.py` -> `11 passed`
2. `PYTHONPATH=. .venv/bin/python -m pytest -q tests` -> `49 passed`

## 4. 주요 결과
- 분석 샘플:
1. `target_count`: 150
2. `raw_count`: 460
3. `dedup_count`: 297
4. `analyzed_count`: 150

### 4.1 robots/fetch 정책별 성공률 비교
1. `blocklist_fallback`: `62/142` -> `0.4366`
2. `direct_fetch`: `2/7` -> `0.2857`
3. `fallback_after_fetch_error`: `0/1` -> `0.0000`

### 4.2 실패 상위 도메인 Top10(핵심)
1. `news.google.com` 실패 `80` (주요 원인 `NO_NUMERIC_SIGNAL` 70)
2. `www.newsis.com` 실패 `3` (주요 원인 `NO_TITLE_CANDIDATE_SIGNAL` 3)
3. `www.yna.co.kr` 실패 `1` (주요 원인 `POLICY_ONLY_SIGNAL`)
4. `www.khan.co.kr` 실패 `1` (주요 원인 `POLICY_ONLY_SIGNAL`)
5. `www.hankyung.com` 실패 `1` (주요 원인 `PARSE_EMPTY_OR_SHORT_BODY`)

### 4.3 개선 우선순위 Top5
1. `news.google.com` / `NO_NUMERIC_SIGNAL`
- 개선안: 본문 후보/수치 패턴(표기 변형, 구분자) 규칙 보강
2. `www.newsis.com` / `NO_TITLE_CANDIDATE_SIGNAL`
- 개선안: 실패 샘플 수집 후 파서/매핑 규칙 점검
3. `www.yna.co.kr` / `POLICY_ONLY_SIGNAL`
- 개선안: 정책형 문항 제외 규칙 유지 + 분류 선제 차단
4. `www.khan.co.kr` / `POLICY_ONLY_SIGNAL`
- 개선안: 정책형 문항 제외 규칙 유지 + 분류 선제 차단
5. `www.hankyung.com` / `PARSE_EMPTY_OR_SHORT_BODY`
- 개선안: 본문 클리너 도메인별 예외 규칙 추가

## 5. 완료기준 충족 여부
1. 도메인별 성공률 리포트 1회 생성: 충족
2. 개선 우선순위 Top5 제시: 충족
3. Collector_reports 보고서 1건 제출: 충족

## 6. 의사결정 필요 항목
1. `news.google.com` 비중 처리 정책:
- 현재 분석 샘플에서 `news.google.com` 비중이 매우 큼(142/150)
- 도메인 KPI에서 별도 분리(google 경유 vs 원문 도메인)할지 결정 필요
2. 정책별 목표치(SLO):
- `blocklist_fallback` 및 `direct_fetch` 각각의 최소 성공률 목표치 정의 필요
3. 주간 운영 주기:
- 본 스크립트를 주 1회 고정 실행할지, 배포 전/후 비교 실행할지 결정 필요
