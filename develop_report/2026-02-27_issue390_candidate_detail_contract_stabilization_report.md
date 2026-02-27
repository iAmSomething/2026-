# 2026-02-27 Issue #390 후보 상세 API 결측/출처 계약 안정화 보고서

## 1) 이슈
- #390 `[W7][DEVELOP][P2] 후보 상세 API 결측/출처 계약 안정화`

## 2) 구현 내용
1. `/api/v1/candidates/{candidate_id}` 응답 계약 보강
- 신규 필드
  - `profile_source`: `data_go|ingest|mixed|none`
  - `profile_completeness`: `complete|partial|empty`
  - `profile_provenance`: 프로필 필드별 출처(`data_go|ingest|missing`)
  - `profile_source_type`, `profile_source_url`
  - `placeholder_name_applied`

2. 결측/placeholder 정책 표준화
- 문자열 결측(`''`, 공백)은 `null`로 정규화
- `name_ko` 결측 시 `candidate_id`로 fallback
- fallback 적용 여부를 `placeholder_name_applied`로 명시

3. provenance 계산 로직 추가
- 기준 필드: `party_name`, `gender`, `birth_date`, `job`, `career_summary`, `election_history`
- base(DB) vs enriched(data.go 반영 후) 비교로 필드별 출처 계산

4. repository 매핑 보강
- `get_candidate` 조회에 `candidate_profiles.source_type/source_url` 포함

5. 문서 업데이트
- `docs/02_DATA_MODEL_AND_NORMALIZATION.md`
- `docs/03_UI_UX_SPEC.md`

## 3) 테스트
- 실행:
```bash
/Users/gimtaehun/election2026_codex/.venv/bin/python -m pytest -q \
  tests/test_api_routes.py tests/test_data_go_candidate_service.py
```
- 결과: `38 passed`

- 추가/강화 검증
1. data.go 병합 시 provenance/source 집계 검증
2. 결측 프로필에서 null 정규화 및 placeholder 플래그 검증
3. 기존 후보 상세 계약/회귀 동작 유지

## 4) 변경 파일
- `app/api/routes.py`
- `app/models/schemas.py`
- `app/services/repository.py`
- `tests/test_api_routes.py`
- `docs/02_DATA_MODEL_AND_NORMALIZATION.md`
- `docs/03_UI_UX_SPEC.md`
- `develop_report/2026-02-27_issue390_candidate_detail_contract_stabilization_report.md`

## 5) 수용기준 대응
1. 후보 상세 API 4xx/5xx 회귀 0
- 대상 테스트 PASS 및 기존 엔드포인트 회귀 없음
2. 결측 표현 일관
- 공백 문자열 null 정규화 + 이름 placeholder 정책 고정
3. UI 연동 QA PASS
- 출처/완결성/placeholder 계약 키를 응답에 명시해 분기 기준 단순화
