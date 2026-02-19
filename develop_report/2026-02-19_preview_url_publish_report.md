# 2026-02-19 Preview URL Publish Report

## 1. 목적
- Issue #92 `[DEVELOP] 외부 프리뷰 URL 발급(비차단 병렬트랙)` 대응
- 배포 타깃 `Vercel`, 배포 방식 `CI`, 토큰은 GitHub Secrets로만 주입

## 2. 구현 결과
1. Preview 배포 워크플로 추가
- 파일: `.github/workflows/vercel-preview.yml`
- 트리거: `workflow_dispatch`
- 입력값:
  - `root_dir` (`apps/staging-web` | `apps/web`)
  - `issue_number` (기본값 `92`)

2. 보안/운영 강제
- 필수 Secret 미주입 시 fail-fast:
  - `VERCEL_TOKEN`
  - `VERCEL_SCOPE` (team slug)
  - `VERCEL_PROJECT_NAME`
- 민감값 출력 금지(Secret 원문 로그 미출력)

3. 자동화 동작
- 웹 빌드 성공 후 `vercel deploy` 실행
- 배포 로그에서 Preview URL 추출
- `curl` 접근 확인 수행
- 액션 artifact 업로드:
  - `/tmp/vercel-preview-deploy.log`
  - `/tmp/vercel-preview-home.html`
- 성공 시 지정 이슈에 URL 자동 코멘트

4. 문서 동기화
- 파일: `docs/04_DEPLOYMENT_AND_ENVIRONMENT.md`
- 섹션 추가: `12. Vercel Preview CI (Issue #92)`

## 3. 로컬 검증
1. 명령
- `npm --prefix apps/staging-web ci`
- `npm --prefix apps/staging-web run build`
2. 결과
- build 성공

## 4. 현재 상태
- CI 파이프라인 준비 완료
- 실제 외부 Preview URL 발급은 아래 Secret 값 주입 후 `workflow_dispatch` 실행 시 완료

## 5. 오너 입력 필요(의사결정)
1. `VERCEL_SCOPE` 실제 값 확정 (`<team_slug>` 대체)
2. `VERCEL_PROJECT_NAME` 실제 값 확정 (`<project_name>` 대체)
3. 기본 root_dir 확정 권고:
- 현재 main 기준 빌드 가능한 경로는 `apps/staging-web`
- `apps/web`는 `package.json` 부재로 현재 배포 불가

## 6. 후속 액션(DEVELOP)
1. Secret 주입 확인
2. `Vercel Preview` 워크플로 실행 (`root_dir=apps/staging-web`, `issue_number=92`)
3. 발급 URL/접근 검증 로그를 이슈 #92 코멘트 및 본 보고서에 최종 반영
