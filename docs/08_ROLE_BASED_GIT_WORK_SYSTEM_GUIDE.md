# 역할별 Git 업무분담 시스템 설명서

- 문서 버전: v0.1
- 최종 수정일: 2026-02-18
- 작성자: 기획자(Codex)

## 1. 목적
- UIUX/Collector/Develop 3개 담당자가 병렬로 작업해도 충돌 없이 진행하도록 GitHub 중심 운영 규칙을 고정한다.
- 보고서 파일, Issue, PR, 리뷰, 피드백 루프를 한 흐름으로 연결한다.

## 2. 현재 상태 요약 (보고서 반영)
1. UIUX
- v0.2 문서 원문 반영 완료
- `/api/v1` + `snake_case` 계약 반영 완료
- 미구현 API는 mock fixture 준비 완료
- UI 구현 착수는 현재 보류 상태

2. Collector
- 계약 동결(Freeze) 완료
- `region_code`/`office_type` 표준화 완료
- `review_queue` taxonomy 고정 완료
- `.venv` 단일 환경으로 마이그레이션 완료

3. Develop
- API 3개 구현 및 테스트 통과 보고
- Python 3.13 + `.venv` 표준 반영
- 남은 4개 API 구현 및 Supabase 키 rotate가 후속 과제

## 3. 단일 기준 (Single Source of Truth)
1. 기획/계약 문서
- `docs/02_DATA_MODEL_AND_NORMALIZATION.md`
- `docs/03_UI_UX_SPEC.md`
- `docs/04_DEPLOYMENT_AND_ENVIRONMENT.md`
- `docs/06_COLLECTOR_CONTRACTS.md`

2. 작업/상태 관리
- GitHub Issues + Labels + Milestone
- GitHub Actions(PR 규칙 자동검증)

3. 보고서 디렉터리 (경로 고정)
- `UIUX_reports/`
- `Collector_reports/`
- `develop_report/`

## 4. GitHub CLI 운영 절차 (공통)

## 4.1 초기 1회 설정
```bash
bash scripts/pm/bootstrap_github_cli.sh iAmSomething/2026-
```
- 부트스트랩은 PM 주기운영 변수도 기본값으로 설정한다.
  - `PM_CYCLE_MODE=dry-run`
  - `PM_CYCLE_MAX_CREATE=4`
  - `PM_CYCLE_ALLOW_REOPEN_DONE=false`
  - `PM_CYCLE_REOPEN_LOOKBACK_DAYS=7`

## 4.2 작업 생성
```bash
bash scripts/pm/new_task.sh iAmSomething/2026- uiux "작업명" iAmSomething p1
bash scripts/pm/new_task.sh iAmSomething/2026- collector "작업명" iAmSomething p1
bash scripts/pm/new_task.sh iAmSomething/2026- develop "작업명" iAmSomething p1
```

## 4.3 보고서 연결
```bash
bash scripts/pm/link_report_to_issue.sh iAmSomething/2026- <issue_no> <보고서_경로> "요약 메모"
```

## 4.4 브랜치 규칙
- 브랜치명: `codex/<role>/<issue-number>-<slug>`
- 예시: `codex/uiux/1-mvp-home-contract`, `codex/collector/3-code-mapping`, `codex/develop/2-api-4-endpoints`

## 4.5 커밋 규칙
1. 문서 변경과 코드 변경은 분리 커밋
2. 보안 파일(`key.txt`, `supabase_info.txt`, `.env*`)은 커밋 금지
3. 한 PR은 하나의 Issue를 닫는 범위로 유지

## 5. PR/리뷰 규칙 (Actions 자동검증)
1. PR 본문에 `Report-Path: <path>` 필수
2. `Report-Path` 파일은 PR 변경 파일에 반드시 포함
3. 보고서 파일명 형식:
- `YYYY-MM-DD_<topic>_report.md`
4. 보고서 첫 줄은 `# ` 제목 필수
5. Actions:
- `report-governance.yml`
- `report-file-lint.yml`
- `report-summary-comment.yml`

## 6. 담당자별 실행 지침

## 6.1 UIUX 담당자
1. 입력 기준
- `docs/03_UI_UX_SPEC.md`
- `UIUX_reports/ALIGNMENT_PATCH_UIUX_v0.2.md`
2. 산출물
- 화면/상태/API-필드 매핑 문서
- 필요 시 fixture JSON 업데이트
- 보고서: `UIUX_reports/YYYY-MM-DD_<topic>_report.md`
3. 완료 체크
- `/api/v1` 경로만 사용
- 서버 계약 필드는 `snake_case`만 사용
- mock과 real API 경계를 문서에 명시

## 6.2 Collector 담당자
1. 입력 기준
- `docs/06_COLLECTOR_CONTRACTS.md`
- `docs/02_DATA_MODEL_AND_NORMALIZATION.md`
2. 산출물
- 수집/추출/정규화/계약 변환 코드
- precision 검증 리포트
- 보고서: `Collector_reports/YYYY-MM-DD_<topic>_report.md`
3. 완료 체크
- `region_code`는 CommonCodeService 체계 준수
- `office_type` 표준값 준수
- `review_queue` taxonomy enum 준수

## 6.3 Develop 담당자
1. 입력 기준
- `docs/02_DATA_MODEL_AND_NORMALIZATION.md`
- `docs/03_UI_UX_SPEC.md`
- `docs/04_DEPLOYMENT_AND_ENVIRONMENT.md`
2. 산출물
- API/DB/CLI 구현
- 테스트 로그
- 보고서: `develop_report/YYYY-MM-DD_<topic>_report.md`
3. 완료 체크
- Python 3.13 + `.venv` 기준
- API 응답 필드가 UI 계약과 일치
- 키/시크릿은 환경변수/Secret만 사용

## 7. 피드백 루프 (일일)
1. 각 담당자는 Issue comment로 진행상황 3줄 업데이트
2. 차단 이슈는 `status/blocked` 라벨로 전환
3. 해결 후 `status/in-review` -> PR -> `status/done`
4. 최종 판단/변경사항은 `docs/`에 반영 후 close

## 8. 현재 운영상 주의사항
1. Collector 보고서 경로는 `Collector_reports/`로 고정
2. UIUX 보고서는 `UIUX_reports/` 기준으로 유지
3. 자동검증은 지정된 3개 보고서 폴더만 인정

## 9. 빠른 체크리스트
1. 내 작업 Issue가 있는가
2. 내 브랜치가 규칙에 맞는가
3. 보고서 파일명이 규칙에 맞는가
4. PR 본문에 `Report-Path:`를 썼는가
5. 문서 계약과 필드명이 일치하는가

## 10. 운영 듀얼레인 요약
1. 오프라인 자동 레인 전환:
```bash
bash scripts/pm/set_pm_cycle_mode.sh --repo iAmSomething/2026- --lane offline
```
2. 온라인 수동 레인 전환:
```bash
bash scripts/pm/set_pm_cycle_mode.sh --repo iAmSomething/2026- --lane online
```
3. 온라인 세션에서는 `dry-run`으로 현황만 갱신하고, 상태 변경(`apply`)은 근거 코멘트 후 1회 수동 실행 원칙을 따른다.
4. `status/done` 이슈 자동 재오픈은 기본 금지이며, 필요 시 `PM_CYCLE_ALLOW_REOPEN_DONE=true`를 단발성으로만 사용한다.

## 11. 무인 운영(Autopilot) 규칙
1. 자동 디스패치 워크플로:
- `.github/workflows/autonomous-dispatch.yml`
- 주기: 30분
- 대상: `status/ready` + `role/*` 라벨 이슈
- 동작: `status/in-progress` 전환 후 역할별 워크플로 디스패치

2. 역할별 디스패치 매핑:
- `role/collector` -> `ingest-schedule.yml`
- `role/develop` -> `phase1-qa.yml` (`with_db=true`, `with_api=true`)
- `role/uiux` -> `staging-smoke.yml`
- `role/qa` -> `qa-api-contract-suite.yml`

3. 워치독 워크플로:
- `.github/workflows/automation-watchdog.yml`
- 주기: 30분
- 기능: PM Cycle/Ingest Schedule 장시간 미실행 시 자동 재디스패치

4. 운영 변수:
- `AUTO_DISPATCH_MAX` (기본 2)
- `PM_MAX_IDLE_MINUTES` (기본 70)
- `INGEST_MAX_IDLE_MINUTES` (기본 150)

5. 주의:
- 자동화는 이슈를 `in-progress`까지 전진시킨다.
- 최종 완료(`status/done`)는 QA PASS 계약을 만족해야 한다.

## 12. Worktree/Runtime 위생 규칙
1. 정리 대상 패턴:
- `$HOME/election2026_codex_issue*`
- `$HOME/election2026_issue*`
- `$HOME/election2026_runtime*`
- `$HOME/election2026_codex_runtime*`

2. 안전 제외:
- 메인 레포(`election2026_codex`)
- `git worktree list`에 잡히는 활성 worktree 경로

3. 로컬 실행:
```bash
bash scripts/pm/worktree_hygiene.sh --mode dry-run --hours 24 --base-dir "$HOME" --report data/worktree_hygiene_report_local.txt
bash scripts/pm/worktree_hygiene.sh --mode apply --hours 24 --base-dir "$HOME" --report data/worktree_hygiene_report_apply.txt
```

4. 자동화:
- 워크플로: `.github/workflows/worktree-hygiene.yml`
- 스케줄: 주 1회(`dry-run`)
- 수동 실행: `workflow_dispatch`에서 `dry-run/apply` 선택 가능
- 산출물: 정리 후보/제외/삭제 결과를 artifact로 업로드
