# [COLLECTOR][HOTFIX] blocked evidence sync pack 보고서 (#206)

## 1) 목적
운영/통합 게이트 병목 원인인 collector 증빙 미머지를 해소하기 위해,
`#200/#182/#183/#188/#189`의 QA FAIL missing paths를 `main` 기준으로 동기화한다.

## 2) 범위
- 대상 이슈: `#200`, `#182`, `#183`, `#188`, `#189`
- 대상 유형: report/data/script/test 누락 경로 + #200 hotfix workflow 반영 경로

## 3) 반영 결과
- 동기화 완료 파일: 총 30개
- 핵심 그룹:
  - #200: freshness hotfix report/script/test/data + archive + ingest workflow 입력 전환
  - #182: party inference v2 report/script/test/data
  - #183: NESDC adapter v2(5기관) report/script/test/data
  - #188: live coverage v2 report/script/test/data
  - #189: low-confidence triage v1 report/script/test/data

## 4) 검증
실행:
```bash
PYTHONPATH=. /Users/gimtaehun/election2026_codex/.venv/bin/pytest -q \
  tests/test_collector_freshness_hotfix_v1_pack_script.py \
  tests/test_collector_party_inference_v2_batch_script.py \
  tests/test_nesdc_pdf_adapter_v2_5pollsters_script.py \
  tests/test_collector_live_coverage_v2_pack_script.py \
  tests/test_collector_low_confidence_triage_v1_script.py
```

결과:
- `15 passed in 0.14s`

## 5) DoD 체크
1. 5개 이슈 missing paths 0건
- 본 PR에서 QA FAIL에 적시된 missing paths 전부 `main`에 반영 대상 포함.

2. 이슈별 완료 보고 코멘트 계약 준수
- 각 이슈에 `[role/collector] 완료 보고` 형식으로
  `report_path`, `evidence`, `next_status: status/in-review` 코멘트 등록.

3. 운영 게이트 재실행 가능 상태
- #200 freshness hotfix 입력 payload/보고서/워크플로우가 main 기준 재현 가능.

## 6) 산출물
- 본 보고서: `Collector_reports/2026-02-23_hotfix_blocked_evidence_sync_pack_report.md`
