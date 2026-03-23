# [COLLECTOR] Issue #481 스코프 누수 데이터 키셋 재처리 보고서

- 이슈: https://github.com/iAmSomething/2026-/issues/481
- 작성일: 2026-02-27
- 담당: role/collector

## 1) 작업 요약
- 대상 범위: `region_code in {26-710, 28-450}` 이면서 광역시장 누수 키워드(`부산시장`, `인천시장`)가 검출된 observation
- 재처리 방식: ingest hardguard 로직 재적용 결과를 기준으로 observation/region 필드를 교정한 reprocess payload 생성
- 증빙 산출물: keyset, before/after reprocess report JSON, QA probe JSON 생성

## 2) 대상 키셋
- `live30d-v2-12-obs_b61d10f49a5d5fdd`
- `live30d-v2-18-obs_8dc5d149038ab97c`

## 3) before/after 비교
1. `live30d-v2-12-obs_b61d10f49a5d5fdd`
- before: `26-710 / 기초자치단체장 / 2026_local|기초자치단체장|26-710`
- after: `26-000 / 광역자치단체장 / 2026_local|광역자치단체장|26-000`
- article_title: `[2026지방선거] 부산시장, 전재수 43.4-박형준 32.3%, 전재수 43.8%-김도읍33.2%...다자대결 전재수26.8% 선두`
- canonical_title(before→after): `기장군수 → 부산시장`

2. `live30d-v2-18-obs_8dc5d149038ab97c`
- before: `28-450 / 기초자치단체장 / 2026_local|기초자치단체장|28-450`
- after: `28-000 / 광역자치단체장 / 2026_local|광역자치단체장|28-000`
- article_title: `[여론조사] 인천시장 양자대결 박찬대 51.2%, 유정복 37.1% 오차 밖 앞서`
- canonical_title(before→after): `연수구청장 → 인천시장`

## 4) 수용기준 점검
- [x] 대상 키셋 reprocess 성공
- [x] `28-450/26-710` 누수 키워드 제거
- [x] scope 관련 target probe FAIL 0 (`qa_failure_count=0`)

## 5) 산출물
- `data/issue481_scope_leak_keys.json`
- `data/issue481_scope_leak_reprocess_payload.json`
- `data/issue481_scope_leak_reprocess_report.json`
- `data/issue481_scope_leak_qa_probe.json`
- `scripts/run_issue481_scope_leak_reprocess.py`
- `tests/test_issue481_scope_leak_reprocess_script.py`

## 6) 검증
- 테스트: `/Users/gimtaehun/election2026_codex/.venv/bin/python -m pytest tests/test_issue481_scope_leak_reprocess_script.py -q`
- 결과: `1 passed`
- 스크립트 실행: `/Users/gimtaehun/election2026_codex/.venv/bin/python scripts/run_issue481_scope_leak_reprocess.py`
- 결과: `target_record_count=2`, `qa_failure_count=0`

## 7) 의사결정 필요사항
1. 이슈 본문의 참고 기사(`idxno=719065`)는 현재 저장소 데이터셋에서 조회되지 않았습니다.
- 현재 리포트는 live coverage v2 payload 기준 누수키 2건으로 재처리 증빙을 작성했습니다.
- `idxno=719065`를 반드시 포함해야 하면 원본 payload/observation_key 공유가 필요합니다.
