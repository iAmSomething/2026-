# 2026-02-26 Issue331 Summary Representative Selection Report

## 1) 목표
- `/api/v1/dashboard/summary`에서 option별 대표값 1건만 반환
- source 우선순위 기반 선택: official > nesdc > article_aggregate > article
- 동률 시 최신 조사일, 그 다음 source_grade 점수로 선택
- 선택근거 필드 응답 포함

## 2) 변경 사항

### A. 대표값 선택 로직 추가
- 파일: `app/api/routes.py`
- 추가:
  - source tier 판정 함수
  - row 우선순위 key(티어 > 조사일 > source_grade)
  - option 단위 그룹핑 후 대표 row 선별
- 적용 대상:
  - `party_support`
  - `president_job_approval`
  - `election_frame`
  - `presidential_approval`(deprecated)도 동일 대표값으로 동기화

### B. 선택근거 필드 추가
- 파일: `app/models/schemas.py`
- `SummaryPoint` 확장:
  - `selected_source_tier`
  - `selected_source_channel`

### C. summary 쿼리 보강
- 파일: `app/services/repository.py`
- `fetch_dashboard_summary()` SELECT에 `source_grade` 포함
  - 동률 시 신뢰도 우선순위 계산에 사용

## 3) 테스트
- 파일: `tests/test_api_routes.py`
- 신규 테스트:
  - `test_dashboard_summary_selects_single_representative_by_source_priority`
- 검증 포인트:
  - 옵션별 1건 반환
  - `더불어민주당`은 article 최신값보다 nesdc값 우선 선택
  - `국민의힘`은 article 대비 article_aggregate 우선 선택
  - 동률 상황에서 source_grade 높은 row 선택
  - `selected_source_tier/channel` 응답 포함

### 실행 결과
- 명령: `/Users/gimtaehun/election2026_codex/.venv/bin/python -m pytest -q tests/test_api_routes.py`
- 결과: `24 passed`

## 4) 수용기준 매핑
- party_support / president_job_approval / election_frame 모두 option당 단일 대표값 반환
- source 우선순위 반영 + 최신일 + source_grade tie-break 적용
- 선택근거 필드 응답 포함

## 5) 반영 파일
- `app/api/routes.py`
- `app/models/schemas.py`
- `app/services/repository.py`
- `tests/test_api_routes.py`
