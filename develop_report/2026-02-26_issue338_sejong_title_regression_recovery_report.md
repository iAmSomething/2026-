# [DEVELOP] Issue #338 세종(29-000) 라벨 회귀 재복구 보고서

- 작성일: 2026-02-26
- 이슈: https://github.com/iAmSomething/2026-/issues/338
- 담당: role/develop
- 우선순위: P0

## 1) 배경
QA FAIL 재현:
- `/api/v1/regions/29-000/elections` 응답의 `title`이 `광주광역시 ...`로 노출됨.
- 핵심 수용기준인 `세종` 라벨 정상화가 미충족.

## 2) 원인
이전 패치는 `region` 객체의 `sido_name`만 세종으로 보정했고,
`title`이 `elections.title` 또는 `matchups.title`에서 직접 들어오는 경로는 보정하지 못함.

즉, 공식 토폴로지(`topology=official`)에서도 레거시 오염 타이틀이 그대로 출력됨.

## 3) 수정 사항

### A. 공식 모드 title 최종 보정 계층 추가
- 파일: `app/services/repository.py`
- `apply_official_title_overrides()` 추가
  - `region_code == 29-000`이고 `title`에 `세종`이 없으면
    `derive_placeholder_title(region, office_type)`로 강제 복원
  - 빈 title도 placeholder로 보정

### B. 보정 적용 지점
- `fetch_region_elections()` 결과 row 생성 직전
- `topology_mode == official`일 때 항상 title 보정 적용
- 적용 경로 포함:
  1. `elections` 마스터 row 기반 title
  2. `matchups` row 기반 title
  3. placeholder 생성 경로

## 4) 테스트

### 추가 테스트
- 파일: `tests/test_repository_region_elections_master.py`
1. `test_region_elections_official_rewrites_legacy_gwangju_title_from_master_rows`
2. `test_region_elections_official_rewrites_legacy_gwangju_title_from_matchup_rows`

### 실행 결과
- `/Users/gimtaehun/election2026_codex/.venv/bin/pytest tests/test_repository_region_elections_master.py -q` -> `8 passed`
- `/Users/gimtaehun/election2026_codex/.venv/bin/pytest tests/test_api_routes.py -q` -> `25 passed`

## 5) 변경 파일
- `app/services/repository.py`
- `tests/test_repository_region_elections_master.py`
- `develop_report/2026-02-26_issue338_sejong_title_regression_recovery_report.md`

## 6) 의사결정 필요 사항
1. 29-000 title 정책 고정 여부
- 현재는 `세종` 미포함 타이틀을 무조건 placeholder로 교체.
- 향후 세종 타이틀 커스텀 문구를 허용하려면 정책 예외 키워드 목록이 필요.

2. 운영 재검증 시점
- 코드 머지 후 운영 API가 최신 커밋으로 배포되지 않으면 QA 재검증이 무효.
- Railway 배포 SHA 확인 절차를 QA 시작 조건으로 고정할지 결정 필요.
