# GitHub CLI 협업 워크플로

## 목적
- 여러 스레드(UIUX/Collector/Develop/QA)가 같은 저장소에서 병렬 작업할 때,
  이슈/PR/보고서를 CLI 기반으로 일관되게 관리한다.

## 1) 초기 부트스트랩
```bash
bash scripts/pm/bootstrap_github_cli.sh iAmSomething/2026-
```

설정 항목:
1. 공통 라벨(role/status/priority/type)
2. 마일스톤 `Sprint-Week1-MVP`
3. (선택) GitHub Project `Election 2026 Delivery` 생성 시도

## 2) 작업 생성
```bash
bash scripts/pm/new_task.sh iAmSomething/2026- uiux "MVP 홈 화면 상태 정의" iAmSomething p1
bash scripts/pm/new_task.sh iAmSomething/2026- collector "region_code 코드테이블 정합" iAmSomething p0
bash scripts/pm/new_task.sh iAmSomething/2026- develop "map-latest API 구현" iAmSomething p1
bash scripts/pm/new_task.sh iAmSomething/2026- qa "Phase1 계약 검증 및 원인 진단" iAmSomething p1
```

## 3) 보고서 연결
```bash
bash scripts/pm/link_report_to_issue.sh iAmSomething/2026- 12 UIUX_reports/2026-02-19_uiux_mvp_task_report.md "1차 완료"
```

## 3-1) 리포트 스캔
```bash
bash scripts/pm/report_scan.sh
bash scripts/pm/report_scan.sh --date 2026-02-18
```
- QA 보고서는 원인 경로 기반 재할당 제안을 함께 출력한다.

## 4) PR 규칙 (GitHub Action 자동검증)
1. PR 본문에 `Report-Path: <path>` 필수
2. Report-Path 파일은 PR 변경 파일에 반드시 포함
3. 보고서 파일명 규칙: `YYYY-MM-DD_<topic>_report.md`
4. QA 보고서 파일명 규칙: `YYYY-MM-DD_qa_<topic>_report.md`
5. 보고서 첫 줄은 `# ` 제목 필수

## 5) 필요한 폴더
1. `UIUX_reports/`
2. `Collector_reports/`
3. `develop_report/`
4. `QA_reports/`

## 6) 이슈 상태 운영
1. 구현 이슈 기본 흐름: `status/in-progress -> status/in-review -> status/in-qa -> status/done`
2. `status/done` 전환 전 필수 조건: QA PASS 코멘트
3. QA FAIL/WARN이면 원인 진단 기준으로 담당자 재할당 후 `status/in-progress`로 복귀

## 6-1) 작업영역 락 규칙
1. 상세 규칙은 `docs/10_WORKSPACE_LOCK_POLICY.md`를 기준으로 적용
2. 공용 잠금 경로(`docs/**`, `.github/**`, `scripts/pm/**`, `README.md`) 수정은 PM 승인 코멘트 필수
3. 역할별 이슈 템플릿의 Workspace Lock Checklist 체크 후 작업 시작

## 7) 권한 이슈
- `gh project` 사용 시 아래 스코프가 필요할 수 있음:
```bash
gh auth refresh -s read:project -s project
```

## 8) PM 반복 루프 자동화 (Dry Run)
```bash
bash scripts/pm/pm_cycle_dry_run.sh --repo iAmSomething/2026-
bash scripts/pm/pm_cycle_dry_run.sh --repo iAmSomething/2026- --date 2026-02-18
bash scripts/pm/pm_cycle_dry_run.sh --repo iAmSomething/2026- --comment-issue 19
bash scripts/pm/pm_cycle_dry_run.sh --repo iAmSomething/2026- --mode apply --max-create 2
```

동작:
1. 보고서/UIUX/Collector/Develop/QA 최신 상태 스캔
2. 이슈 open/closed/blocked/ready 현황 집계
3. `closed + status/done + [QA PASS] 미기재` 항목 검출
4. QA 보고서의 원인 경로 기준 담당자 재할당 힌트 출력
5. 결과를 `reports/pm/pm_cycle_dry_run_<timestamp>.md`로 저장

GitHub Actions:
1. 워크플로: `.github/workflows/pm-cycle-dry-run.yml`
2. 트리거: 2시간 주기 + 수동 실행(`workflow_dispatch`)
3. 입력값: `mode(dry-run|apply)`, `max_create`, `date_filter`, `comment_issue`
4. Repository Variables:
   - `PM_CYCLE_MODE` (기본 `dry-run`, 필요시 `apply`)
   - `PM_CYCLE_MAX_CREATE` (기본 `4`)
   - `PM_CYCLE_ISSUE_NUMBER` (지정 시 요약 자동 코멘트)
5. `apply` 모드 자동 반영 범위:
   - `closed + status/done + [QA PASS] 미기재` 이슈를 `status/in-qa`로 복귀(재오픈)
   - `status/blocked` 이슈 일일 자동 리마인드 코멘트
   - QA FAIL 보고서 기반 후속 버그 이슈 자동 생성(중복 방지 `auto_key`, 최대 생성 건수 제한)
