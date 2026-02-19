# 2026-02-19 Artifact Tracking And Coverage Semantics Policy Report

## 1) 목적
- 실행 산출물 추적 정책을 명확히 고정하고,
- `GET /api/v1/ops/coverage/summary`의 의미를 누적 집계로 문서에 확정한다.

## 2) 결정 사항 (확정)
1. 데이터 추적 정책
- 재현용 입력 데이터: Git 추적 유지
- 실행 산출물(JSON/PM run report): 기본 Git 비추적
- 공유 경로: Actions artifact 또는 이슈 코멘트 첨부 우선

2. 커버리지 API 의미
- `GET /api/v1/ops/coverage/summary`는 기본 누적 집계(cumulative)
- 기간 필터 없는 전체 커버리지 스냅샷을 운영 기준으로 사용

## 3) 반영 파일
1. `.gitignore`
- 추가:
  - `reports/pm/`
  - `data/*_apply_report.json`
  - `data/*_issue*.json`
  - `data/ingest_schedule_report.json`
  - `data/bootstrap_ingest_dir_report.json`

2. `README.md`
- `ops/coverage/summary` 설명에 `누적 집계` 명시
- `데이터 추적 정책` 섹션 추가

3. `docs/05_RUNBOOK_AND_OPERATIONS.md`
- 지표 API 해석 기준에 누적 집계 의미 명시
- `실행 산출물 관리 정책` 섹션 추가

## 4) 운영 영향
1. 개발자는 입력 데이터만 버전 관리하고, 실행 산출물은 커밋 대상에서 제외한다.
2. 운영 대시보드의 커버리지 지표는 전체 누적 상태를 기준으로 해석한다.
