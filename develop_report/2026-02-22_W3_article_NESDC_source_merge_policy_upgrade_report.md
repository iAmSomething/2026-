# 2026-02-22 W3 기사 NESDC 소스 병합 규칙 고도화 report

## 1. 요약
- 이슈: `#184 [DEVELOP][W3] poll provenance 다중소스 병합 정책 v2`
- 목표: 기사/NESDC 다중소스 병합 시 오탐 충돌을 줄이고, provenance 품질값이 역전되지 않도록 병합 규칙을 강화

## 2. 구현
1. fingerprint 병합 정책 v2 반영
- 파일: `app/services/fingerprint.py`
- 핵심 변경
  - core 충돌 비교(`region_code`, `office_type`, `survey_start_date`, `survey_end_date`, `sample_size`)에 정규화 적용
    - 날짜 포맷 통일(`YYYY-MM-DD`, `YYYY/MM/DD`, `YYYYMMDD`)
    - `sample_size` 숫자형 정규화
    - `region_code` 공백/대소문자 보정
  - `source_channels` 문자열 입력(`"{article,nesdc}"`, `"article,nesdc"`)도 안전하게 파싱
  - `source_grade` 병합을 품질 우선(`A>B>C>D`)으로 변경
    - 후행 `article` 저등급 값이 들어와도 `NESDC` 고등급 값이 다운그레이드되지 않음

2. 테스트 보강
- 파일: `tests/test_poll_fingerprint.py`
- 추가 케이스
  - 타입/포맷만 다른 코어 필드가 병합 성공하는지 검증
  - 후행 저등급 소스 유입 시 `source_grade`가 하향되지 않는지 검증

3. 정책 문서 갱신
- 파일: `docs/02_DATA_MODEL_AND_NORMALIZATION.md`
- 반영 항목
  - 코어 충돌 정규화 비교 규칙 명시
  - `source_grade` 품질 우선 병합 규칙 명시

## 3. 검증
1. 회귀 테스트
- 명령: `/Users/gimtaehun/election2026_codex/.venv/bin/python -m pytest tests/test_poll_fingerprint.py tests/test_ingest_service.py tests/test_repository_source_channels.py tests/test_api_routes.py`
- 결과: `22 passed`

2. API 계약 회귀
- 명령: `bash scripts/qa/run_api_contract_suite.sh --report data/qa_api_contract_report_issue184.json`
- 결과: `total=28, pass=28, fail=0`

## 4. 증빙 파일
- `data/verification/issue184_provenance_merge_pytest.log`
- `data/verification/issue184_provenance_merge_contract_suite.log`
- `data/verification/issue184_api_contract_report.json`
- `data/verification/issue184_api_contract_report_digest.json`
- `data/verification/issue184_provenance_merge_policy_v2.json`

## 5. DoD 체크
- [x] 구현/설계/검증 반영
- [x] 보고서 제출
- [x] 이슈 코멘트에 report_path/evidence/next_status 기재 예정
