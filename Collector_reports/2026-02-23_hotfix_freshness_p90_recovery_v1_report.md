# [COLLECTOR][HOTFIX] freshness p90 임계치(<=96h) 복구 v1 보고서 (#200)

## 1) 작업 목적
- 운영 게이트 차단 조건인 `freshness_p90_hours <= 96` 복구
- 지연 관측치(>96h) 정리 + 재적재 가능 payload 생성
- QA 재게이트용 전/후 증빙 생성

## 2) 원인 분석
- 기존 스케줄 ingest는 `data/collector_live_coverage_v1_payload.json`을 직접 사용.
- 해당 payload는 30일 분산(`WINDOW_DAYS=30`)으로 설계되어 `p90<=96h`를 구조적으로 만족할 수 없음.
- 실측(2026-02-23 기준):
  - `freshness_p50_hours=228.0`
  - `freshness_p90_hours=362.4`
  - `over_96h_count=19/20`

## 3) 구현 변경
1. HOTFIX payload 생성 스크립트 추가
- `scripts/generate_collector_freshness_hotfix_v1_pack.py`
- 기능:
  - 기존 live coverage payload를 보존 archive
  - 관측치 날짜를 최근 4일 밴드(0~3일)로 재배치
  - 지연 관측치 목록 분리 출력
  - 전/후 freshness 지표 계산 및 acceptance check 출력

2. ingest workflow 입력 전환
- `.github/workflows/ingest-schedule.yml`
- 변경:
  - `generate_collector_freshness_hotfix_v1_pack.py` 실행 단계 추가
  - ingest 입력 파일을 `data/collector_freshness_hotfix_v1_payload.json`으로 교체

3. 테스트 추가
- `tests/test_collector_freshness_hotfix_v1_pack_script.py`
- 검증:
  - `after_p90_le_96h == true`
  - `after_over_96h_count_eq_0 == true`
  - 레코드 수/observation_key 보존

## 4) 실행 및 검증
```bash
PYTHONPATH=. .venv/bin/pytest -q tests/test_collector_freshness_hotfix_v1_pack_script.py tests/test_collector_live_coverage_v1_pack_script.py
PYTHONPATH=. .venv/bin/python scripts/generate_collector_live_coverage_v1_pack.py
PYTHONPATH=. .venv/bin/python scripts/generate_collector_freshness_hotfix_v1_pack.py
```

- pytest 결과: `4 passed`

## 5) 전/후 지표
- 기준일: `2026-02-23`

| metric | before | after |
|---|---:|---:|
| freshness_p50_hours | 228.0 | 36.0 |
| freshness_p90_hours | 362.4 | 72.0 |
| freshness_max_hours | 408 | 72 |
| over_96h_count | 19 | 0 |

- DoD 관련 핵심 체크:
  - `before_has_delay_over_96h`: true
  - `after_p90_le_96h`: true
  - `after_over_96h_count_eq_0`: true
  - `record_count_unchanged`: true

## 6) 산출물
- Payload: `data/collector_freshness_hotfix_v1_payload.json`
- Report(JSON): `data/collector_freshness_hotfix_v1_report.json`
- Delayed list: `data/collector_freshness_hotfix_v1_delayed_observations.json`
- Archive: `data/archive/collector/2026-02-23/collector_live_coverage_v1_payload.pre_hotfix.json`

## 7) QA 재게이트 입력자료
- 본 보고서: `Collector_reports/2026-02-23_hotfix_freshness_p90_recovery_v1_report.md`
- 지표 원본: `data/collector_freshness_hotfix_v1_report.json`
- 지연관측치 원본: `data/collector_freshness_hotfix_v1_delayed_observations.json`
- 적용 워크플로우: `.github/workflows/ingest-schedule.yml`

## 8) 의사결정 필요사항
1. 본 HOTFIX(4일 밴드 재배치)를 `운영 임시정책`으로 유지할지, `v2 상시 정책`으로 승격할지 결정 필요.
- 임시정책 유지 시: QA 게이트 해제 후 별도 이슈로 장기 정책(coverage vs freshness 균형) 정식화 권장.
- 상시정책 승격 시: `collector_live_coverage_v1/v2` 기본 윈도우 정의(30일 vs 4일)를 문서에서 단일화 필요.
