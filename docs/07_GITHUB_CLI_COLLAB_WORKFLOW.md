# GitHub CLI 협업 워크플로

## 목적
- 여러 스레드(UIUX/Collector/Develop)가 같은 저장소에서 병렬 작업할 때,
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
```

## 3) 보고서 연결
```bash
bash scripts/pm/link_report_to_issue.sh iAmSomething/2026- 12 UIUX_reports/2026-02-19_uiux_mvp_task_report.md "1차 완료"
```

## 4) PR 규칙 (GitHub Action 자동검증)
1. PR 본문에 `Report-Path: <path>` 필수
2. Report-Path 파일은 PR 변경 파일에 반드시 포함
3. 보고서 파일명 규칙: `YYYY-MM-DD_<topic>_report.md`
4. 보고서 첫 줄은 `# ` 제목 필수

## 5) 필요한 폴더
1. `UIUX_reports/`
2. `Collector_reports/`
3. `develop_report/`

## 6) 권한 이슈
- `gh project` 사용 시 아래 스코프가 필요할 수 있음:
```bash
gh auth refresh -s read:project -s project
```
