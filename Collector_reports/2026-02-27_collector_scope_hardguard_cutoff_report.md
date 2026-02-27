# 2026-02-27 Issue #465 실행 보고서 (Collector)

## 1) 작업 개요
- 이슈: `#465` `[COLLECTOR][P0] 광역시장/도지사 스코프 하드가드 + 기사컷오프(2025-12-01) 적용`
- 목표:
  - 시장/지사 키워드 기사에서 `광역자치단체장 + xx-000` 하드가드 강제
  - 기사 컷오프(`published_at >= 2025-12-01`) 미달 건 ingest 차단 및 로그 일관화(`reason=old_article_cutoff`)
  - `다자대결` 문구인데 후보 저장이 3인 미만이면 review_queue 라우팅(`scenario_parse_incomplete`)

## 2) 반영 내용
- 스코프 하드가드 추가 (`app/services/ingest_service.py`)
  - `SCOPE_HARDGUARD_NEEDLES` 기반 키워드 매칭
  - 하드가드 적용 시 강제 정규화:
    - `office_type=광역자치단체장`
    - `region_code={시도}-000`
    - `matchup_id` 재조립(`{election_id}|광역자치단체장|{xx-000}`)
  - `region` payload 동시 보정:
    - `region_code`를 시도코드로 교정
    - `sigungu_name=전체`, `admin_level=sido`, `parent_region_code=None`

- 기사 컷오프 reason 고정 (`app/services/ingest_service.py`)
  - 차단 review note를 아래 형식으로 고정:
    - `ARTICLE_PUBLISHED_AT_CUTOFF_BLOCK reason=old_article_cutoff policy_reason=PUBLISHED_AT_BEFORE_CUTOFF ...`
  - 런타임 로그도 동일 reason으로 출력

- 시나리오 보전 가드 추가 (`app/services/ingest_service.py`)
  - `survey_name/article.title/article.raw_text`에 `다자대결` 포함 + 후보 저장(`candidate|candidate_matchup`) 유니크 3인 미만 시:
    - `review_queue(issue_type=scenario_parse_incomplete)` 삽입

## 3) 테스트 반영
- 수정: `tests/test_ingest_service.py`
  - 컷오프 review note에 `reason=old_article_cutoff` 및 `policy_reason` 검증 추가
  - 스코프 하드가드 강제 보정 테스트 추가
  - `scenario_parse_incomplete` 라우팅 테스트 추가
- 추가: `tests/test_collector_scope_hardguard_cutoff_eval_script.py`
  - 30건 평가 스크립트 산출/수용기준 체크 자동화

## 4) 검증 결과
- 실행 명령:
  - `/Users/gimtaehun/election2026_codex/.venv/bin/python -m pytest tests/test_ingest_service.py tests/test_collector_scope_hardguard_cutoff_eval_script.py -q`
  - `PYTHONPATH=. /Users/gimtaehun/election2026_codex/.venv/bin/python scripts/generate_collector_scope_hardguard_cutoff_eval.py`
- 결과:
  - `27 passed`
  - 산출물 생성 완료

## 5) 증적 파일
- `data/issue465_scope_hardguard_cutoff_eval.json`
- `data/issue465_scope_hardguard_cutoff_eval_samples.json`

핵심 지표:
- `sample_count`: `30` (수용기준 `>=30` 충족)
- `keyword_record_count`: `14`
- `keyword_violation_count`: `0`
- `old_article_record_count`: `1`
- `old_article_ingested_count`: `0`
- `old_article_cutoff_review_count`: `1`
- `scenario_parse_incomplete_review_count`: `1`

## 6) 수용기준 대응
1. 시장/지사 키워드 포함 기사에서 `기초자치단체장` 생성 0건
- 평가셋 키워드 14건에서 위반 0건 확인

2. 컷오프 미달 기사 라이브 ingest 0건
- 컷오프 미달 1건 강제 주입, ingest 0건 + review note `reason=old_article_cutoff` 확인

3. 다자 문구 기사에서 3인 미만 저장 시 review_queue 생성
- 강제 케이스에서 `scenario_parse_incomplete` 1건 생성 확인

## 7) 의사결정 요청
1. 이슈 본문의 "폴리뉴스 719065 포함 30건" 검증 항목:
- 현재 저장소/데이터셋에서 `719065` 식별자(URL 포함)를 확인하지 못했습니다.
- 질문: 운영에서 사용하는 원본 URL/식별자를 추가 제공해주시면 동일 검증셋으로 재실행해 보고서에 반영하겠습니다.
