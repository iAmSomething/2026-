# 2026-02-19 Batch Bootstrap Ingest Runner Report (Issue #42)

## 1) 이슈
- 대상: `#42 [DEVELOP] 초기 데이터 부트스트랩 실행기(배치 ingest + 요약 리포트) 구현`
- 목표: 파일/디렉토리 입력 기반 다건 적재 실행기와 운영 요약 리포트(JSON) 제공

## 2) 구현 내용
1. 배치 실행기 추가
- 파일: `app/jobs/bootstrap_ingest.py`
- 엔트리포인트:
  - `python -m app.jobs.bootstrap_ingest --input <file|dir> --report <json>`
- 지원 기능:
  - 단일 파일 또는 디렉토리(`--pattern`) 입력
  - JSON 객체(단일 payload) + JSON 배열(복수 payload) 모두 처리
  - payload별 `ingest_payload` 실행 및 run 결과 집계

2. run summary JSON 필드 제공
- 상위 필드:
  - `total`, `success`, `fail`, `review_queue_count`
  - `payload_count`, `run_count`, `runs[]`, `started_at`, `finished_at`
- `review_queue_count`는 실행 전/후 카운트 차이(`review_queue_total_after - before`)로 계산

3. repository 보강
- 파일: `app/services/repository.py`
- 추가 메서드:
  - `count_review_queue()`

4. 테스트 추가
- 파일: `tests/test_bootstrap_ingest.py`
- 검증 항목:
  - 파일/디렉토리 입력 탐색
  - 성공/실패 집계(`total/success/fail`) 및 `review_queue_count` 증가

5. 사용법 문서화
- 파일: `README.md`
- 반영:
  - 부트스트랩 배치 실행기 항목 추가
  - 파일 실행/디렉토리 실행 예시 추가
  - 요약 리포트 필수 필드 명시

## 3) 샘플 실행 산출물
1. 샘플 입력 배치
- `data/bootstrap_ingest_batch_2.json`
- 구성: 성공 1건 + 실패 1건(미등록 지역 코드)

2. 샘플 실행 리포트
- `data/bootstrap_ingest_batch_2_report.json`
- 결과:
  - `total=2`
  - `success=1`
  - `fail=1`
  - `review_queue_count=1`

## 4) 검증
1. 핵심 테스트
- 명령: `.venv/bin/pytest -q`
- 결과: `53 passed`

2. API 계약 회귀
- 명령: `scripts/qa/run_api_contract_suite.sh --report data/qa_api_contract_report_issue42.json`
- 결과: `total=25, pass=25, fail=0`

## 5) 완료기준(DoD) 대비
1. 실행기 구현 + 사용법 문서화
- 충족 (`app/jobs/bootstrap_ingest.py`, `README.md`)

2. 샘플 배치 실행 리포트 제출
- 충족 (`data/bootstrap_ingest_batch_2_report.json`)

3. 기존 API 계약/핵심 테스트 회귀 통과
- 충족 (`pytest`, API contract suite 모두 통과)

4. develop_report 제출
- 충족 (본 문서)

## 6) 의사결정 필요사항
1. 디렉토리 입력 실행 시 파일 순서 정책
- 현재는 파일명 오름차순 정렬 실행
- 필요 시 `--sort created_at` 또는 `--shuffle` 옵션 도입 여부 결정 필요
