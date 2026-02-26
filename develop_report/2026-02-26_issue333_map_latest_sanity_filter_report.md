# 2026-02-26 Issue333 Map-Latest Sanity Filter Report

## 1) 목표
- `/api/v1/dashboard/map-latest` 응답에서 비인명/레거시 누수 최종 차단
- collector 누락 상황에서도 API 레벨 안전장치 보장
- 필터링 카운트/사유를 응답으로 노출

## 2) 변경 사항

### A. map-latest 응답 필터 추가
- 파일: `app/api/routes.py`
- 추가 로직:
  - 후보명 토큰 sanity
    - 한글 실명 패턴(`^[가-힣]{2,8}$`) 불일치 차단
    - generic token(`양자대결`, `다자대결`, `오차`, `응답률`, `민주`, `국힘` 등) 차단
  - 타이틀 sanity
    - 2026 이외 연도 포함 제목 차단
    - 레거시 선거 키워드(`대통령선거`, `총선`, `국회의원`) 차단
  - cutoff 기존 정책은 동일 적용
- 노출:
  - `filter_stats.total_count`
  - `filter_stats.kept_count`
  - `filter_stats.excluded_count`
  - `filter_stats.reason_counts`
- 로그:
  - `dashboard_map_latest_sanity total/kept/excluded/reason_counts`

### B. 응답 스키마 확장
- 파일: `app/models/schemas.py`
- `DashboardFilterStatsOut` 추가
- `DashboardMapLatestOut.filter_stats` 필드 추가

## 3) 테스트

### 수정/추가
- 파일: `tests/test_api_routes.py`
- 기존 map-latest 계약 테스트에 `filter_stats` 검증 추가
- 신규 테스트:
  - `test_map_latest_sanity_filter_drops_invalid_candidate_and_legacy_title_rows`
  - 비인명(`김A`), generic(`양자대결`), 레거시 제목(`2022 ...`)이 제외되는지 검증

### 실행 결과
- 명령: `/Users/gimtaehun/election2026_codex/.venv/bin/python -m pytest -q tests/test_api_routes.py`
- 결과: `23 passed`

## 4) 기대 효과
- map-latest 응답에서 `김A/오G/박C/양자대결`류 누수 0으로 수렴
- API 단계에서 후보명/제목 품질 2차 방어 제공
- QA가 필터 사유별 제외 통계를 응답에서 직접 확인 가능

## 5) 리스크 / 후속
- 엄격 필터로 일부 실명 후보가 제외될 수 있음(한글 2~8자 규칙 외 케이스)
- 운영 after 검증은 배포 반영 후 `#334` QA 재게이트에서 확정 필요

## 6) 반영 파일
- `app/api/routes.py`
- `app/models/schemas.py`
- `tests/test_api_routes.py`
