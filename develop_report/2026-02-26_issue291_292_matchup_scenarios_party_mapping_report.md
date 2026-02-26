# 2026-02-26 DEVELOP P0 매치업 후보 정당/시나리오 분리 보고서 (#291, #292)

## 1) 작업 범위
1. #291 `[DEVELOP][P0] 매치업 후보 정당 표시 정확화(후보ID 매핑 + 정당 조인)`
2. #292 `[DEVELOP][P0] 매치업 상세 시나리오 분리(양자/다자) 데이터모델·API 확장`

## 2) 핵심 변경
1. `poll_options` 스키마 확장:
   - `candidate_id`, `party_name`, `scenario_key`, `scenario_type`, `scenario_title` 추가
   - 유니크 키를 `(observation_id, option_type, option_name, scenario_key)`로 교체
2. 적재 파이프라인 확장:
   - `PollOptionInput`/적재 어댑터에 후보/시나리오 필드 전달
   - 시나리오 키 미입력 시 `scenario_key="default"` 기본값 적용
3. 매치업 조회 로직 확장 (`GET /api/v1/matchups/{matchup_id}`):
   - 후보 정당 우선순위 정책 반영: `official(candidates.party_name) > inferred(poll_options.party_name) > unknown(미확정(검수대기))`
   - `options[]` 외에 `scenarios[]` 응답 구조 추가
   - 동일 후보의 다중 시나리오 값이 덮어써지지 않도록 시나리오별 분리 반환
4. 매치업 상세 화면 확장:
   - 시나리오 섹션(`양자대결/다자대결`) 단위 렌더
   - 옵션 행에서 `candidate_id` 기반 후보 상세 링크 사용
   - 정당명(`party_name`) 표시

## 3) 변경 파일
1. `/Users/gimtaehun/election2026_codex/db/schema.sql`
2. `/Users/gimtaehun/election2026_codex/app/models/schemas.py`
3. `/Users/gimtaehun/election2026_codex/app/services/ingest_service.py`
4. `/Users/gimtaehun/election2026_codex/app/services/repository.py`
5. `/Users/gimtaehun/election2026_codex/src/pipeline/ingest_adapter.py`
6. `/Users/gimtaehun/election2026_codex/apps/web/app/matchups/[matchup_id]/page.js`
7. `/Users/gimtaehun/election2026_codex/tests/test_api_routes.py`
8. `/Users/gimtaehun/election2026_codex/tests/test_ingest_adapter.py`
9. `/Users/gimtaehun/election2026_codex/tests/test_ingest_service.py`
10. `/Users/gimtaehun/election2026_codex/tests/test_repository_matchup_legal_metadata.py`
11. `/Users/gimtaehun/election2026_codex/tests/test_repository_matchup_scenarios.py` (신규)
12. `/Users/gimtaehun/election2026_codex/tests/test_schema_party_inference.py`

## 4) 검증
1. 실행:
```bash
/Users/gimtaehun/election2026_codex/.venv/bin/python -m pytest -q
```
2. 결과: `170 passed in 2.05s`

## 5) 완료 기준 대비
1. 후보 식별자 보존 및 API 노출: 완료 (`candidate_id`)
2. 정당 표시 안정화 및 미확정 표준화: 완료 (`미확정(검수대기)`)
3. 양자/다자 시나리오 분리 저장·응답: 완료 (`scenarios[]`)
4. 동일 후보 다중 시나리오 값 비덮어쓰기: 완료 (시나리오 키 기반 유니크/그룹화)

## 6) 의사결정 필요
1. `options[]` 하위호환 필드 제거 시점 확정 필요
   - 현재는 기존 클라이언트 호환을 위해 `scenarios[]`와 병행 제공 중.
2. `scenario_title` 생성 규칙의 단일 표준(collector 단계 선생성 vs API 단계 동적 생성) 확정 필요
   - 현재는 입력 우선, 미입력 시 API에서 동적 생성.
3. 후보명 동명이인 대응 정책 확정 필요
   - 현재는 `candidate_id` 우선 조인, 미지정 시 `option_name` 기반 보조 조인을 수행.
