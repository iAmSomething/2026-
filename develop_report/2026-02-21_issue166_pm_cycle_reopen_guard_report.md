# 2026-02-21 Issue #166 PM Cycle apply 자동 재오픈 회귀 방지 보고서

## 1. 목표
- 기본 정책에서 `status/done` 이슈 자동 재오픈 금지
- 명시적 opt-in 없이는 reopen 로직 실행 금지
- reopen 대상 필터 강화 + 회귀 테스트 추가

## 2. 조치
1. `scripts/pm/pm_cycle_dry_run.sh`
- 새 정책 변수 도입
  - `PM_CYCLE_ALLOW_REOPEN_DONE` (기본 `false`)
  - `PM_CYCLE_REOPEN_LOOKBACK_DAYS` (기본 `7`)
- 새 CLI 옵션
  - `--allow-reopen-done true|false`
  - `--reopen-lookback-days N`
- reopen 실행 가드
  - `MODE=apply`이더라도 `allow_reopen_done=false`면 reopen 미실행
- reopen 대상 필터
  - `scripts/pm/reopen_policy.py` 결과(최근 lookback, closed+done, role label 보유)만 QA PASS 검사
- 리포트에 정책 상태 출력
  - `reopen_policy_enabled`, `reopen_lookback_days`, `reopen_candidates_checked`

2. `scripts/pm/reopen_policy.py` (신규)
- boolean 파싱/시간 파싱 유틸
- reopen 후보 선택 로직(allow flag + lookback + label/state 필터)

3. 워크플로/운영 변수 반영
- `.github/workflows/pm-cycle-dry-run.yml`
  - dispatch input: `allow_reopen_done`, `reopen_lookback_days`
  - repo variable 연동: `PM_CYCLE_ALLOW_REOPEN_DONE`, `PM_CYCLE_REOPEN_LOOKBACK_DAYS`
- `scripts/pm/bootstrap_github_cli.sh`
  - 기본 변수 추가: `PM_CYCLE_ALLOW_REOPEN_DONE=false`, `PM_CYCLE_REOPEN_LOOKBACK_DAYS=7`
- `scripts/pm/set_pm_cycle_mode.sh`
  - lane 전환 시 reopen 가드 변수 기본값 유지
- `docs/08_ROLE_BASED_GIT_WORK_SYSTEM_GUIDE.md`
  - 운영 권장값 및 단발성 opt-in 원칙 문서화

## 3. 회귀 테스트
1. 신규 테스트
- `tests/test_pm_cycle_reopen_policy.py`
  - 기본 비활성화 시 후보 0건
  - allow=true일 때 최근 done+role 이슈만 후보 포함

2. 기존 테스트 포함 재검증
- `tests/test_ingest_runner.py`
- `tests/test_pm_cycle_qafail_detection.py`
- `tests/test_pm_cycle_qapass_detection.py`

3. 실행 결과
- `12 passed`
- `bash -n scripts/pm/pm_cycle_dry_run.sh` 통과

4. 증빙 파일
- `data/verification/issue166_pm_reopen_guard_tests.log`

## 4. 수용 기준 대응
1. 기본 설정에서 done 자동 재오픈 0건: 충족(allow 기본 false + apply guard)
2. 테스트/검증 로그 첨부: 충족
3. 운영 변수 권장값 문서화: 충족
