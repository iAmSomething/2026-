# [DEVELOP] #254 ingest timeout/backoff 운영 표준값 고정 보고서

- 작성일: 2026-02-24
- 담당: role/develop
- 이슈: https://github.com/iAmSomething/2026-/issues/254
- 브랜치: `codex/issue254-timeout-policy`

## 1) 목표
- ingest 재시도 정책(timeout/backoff/retry)을 코드/워크플로/런북에서 단일 기본값으로 고정
- 적용 영향 범위를 `Ingest Schedule`, `Collector Live News Schedule`로 명시
- 최근 런타임 p95 근거를 문서화

## 2) 반영 변경
1. 코드 기본값 고정
- `scripts/qa/run_ingest_with_retry.py`
- `scripts/qa/reprocess_ingest_dead_letter.py`
- `app/jobs/ingest_runner.py`
- 공통 기본값:
  - `max_retries=2`
  - `backoff_seconds=1`
  - `timeout=180`
  - `timeout_scale_on_timeout=1.5`
  - `timeout_max=360`

2. 워크플로 고정값 정렬
- `.github/workflows/ingest-schedule.yml`
  - `--max-retries 2`
  - `--backoff-seconds 1`
  - `--timeout 180`
  - `--timeout-scale-on-timeout 1.5`
  - `--timeout-max 360`
- `.github/workflows/collector-live-news-schedule.yml`
  - 기존 동일값 유지(재확인)

3. 운영 문서 정합성 반영
- `docs/05_RUNBOOK_AND_OPERATIONS.md`
  - `2.3 Ingest Retry Canonical Policy (S6)` 섹션 추가
  - 정책 적용 범위(`Ingest Schedule`, `Collector Live News Schedule`) 명시
  - timeout/backoff 정책 상세와 근거(p95) 명시
- `README.md`
  - 내부 재시도 실행 예시를 표준 파라미터로 업데이트

## 3) p95 근거 (2026-02-24, main 최근 성공 런)
- 수집 방법: `gh run list --workflow <workflow> --branch main --limit 30 --json createdAt,updatedAt,conclusion`
- 계산 방식: 성공 런의 `(updatedAt-createdAt)` 초 단위 nearest-rank p95

1. `Ingest Schedule` (`ingest-schedule.yml`)
- success n=26
- p50=189.5s
- p95=227s
- max=387s
- latest success run: `22337873229`

2. `Collector Live News Schedule` (`collector-live-news-schedule.yml`)
- success n=2
- p50=852s
- p95=856s
- max=856s
- latest success run: `22340131707`

해석:
- 단일 요청 timeout을 180초로 두고 timeout 시 1.5배 스케일(상한 360초) 적용 시 장시간 지연 케이스를 커버
- timeout 계열 실패 시 최소 backoff 5초(`app/jobs/ingest_runner.py`)로 과도한 재호출을 억제

## 4) 검증
1. workflow YAML 파싱
- 실행: `bash scripts/qa/validate_workflow_yaml.sh`
- 결과: pass

2. Python 문법 검증
- 실행: `python3 -m py_compile app/jobs/ingest_runner.py scripts/qa/run_ingest_with_retry.py scripts/qa/reprocess_ingest_dead_letter.py`
- 결과: pass

3. 테스트 실행 여부
- `pytest`/`.venv/bin/pytest`가 해당 작업트리에 없어 단위테스트는 미실행
