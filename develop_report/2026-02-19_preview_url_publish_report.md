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
- `curl` 접근 확인 수행(공개 접근 `2xx/3xx` 또는 auth-gated `401`)
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

## 4. 실행 결과 (완료)
1. 최종 성공 실행
- Action Run: `https://github.com/iAmSomething/2026-/actions/runs/22176343247`
- 결과: `success`
- root_dir: `apps/staging-web`
2. 발급 URL
- preview_url: `https://2026-deploy-epnimvys2-st939823s-projects.vercel.app`
3. 접근 검증
- access_mode: `auth_gated`
- status_code: `401`
- 증빙 코멘트: `https://github.com/iAmSomething/2026-/issues/92#issuecomment-3925761666`

## 5. 장애/개선 이력
1. 초기 실패 원인
- Vercel project rootDirectory 설정과 workflow `working-directory`가 중복되어 경로가 `apps/staging-web/apps/staging-web`로 깨짐
2. 개선
- Deploy step을 저장소 루트 실행으로 수정
- 접근 검증을 `401(auth-gated)` 허용 형태로 보완

## 6. 결론
1. Issue #92의 Preview URL 발급 및 이슈 고정 코멘트까지 완료
2. 접근 검증 로그/액션 런 증빙 확보 완료
