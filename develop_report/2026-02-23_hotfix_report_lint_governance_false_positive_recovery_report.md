# 2026-02-23 HOTFIX report lint/governance 오탐 복구 보고서 (#213)

## 1) 배경
- report lint가 `UIUX_reports|Collector_reports|develop_report` 경로의 모든 변경 파일을 검사하여, 스크린샷(`.png`)에도 markdown 파일명/헤더 규칙을 적용하는 오탐이 발생했습니다.
- report governance는 PR 본문의 `- Report-Path: ...`(불릿형) 문구를 파싱하지 못해 유효한 입력도 누락으로 처리될 수 있었습니다.

## 2) 조치
1. report lint 범위 축소
- 파일: `.github/workflows/report-file-lint.yml`
- 변경: lint 대상 파일을 `*_report.md`로 제한
- 결과: 스크린샷/비-md 파일은 lint 검사 대상에서 제외

2. governance 파서 완화
- 파일: `.github/workflows/report-governance.yml`
- 변경: `Report-Path:`와 `- Report-Path:`를 모두 허용하고, backtick 경로 표기도 허용
- 변경: 에러 메시지에 예시 경로 포함

3. 안내 코멘트 자동화 추가
- 파일: `.github/workflows/report-governance.yml`
- 변경: 검증 실패 시 PR에 가이드 코멘트를 자동 등록(중복 방지 marker 포함)

4. PR 템플릿 보강
- 파일: `.github/pull_request_template.md`
- 변경: `Report-Path` 항목을 불릿 없는 표준 라인으로 수정

## 3) 재검증 전략
- 동일 유형(스크린샷 포함) 조건 재현을 위해 probe png 파일을 PR 변경분에 포함
- lint/governance 체크 green 확인

## 4) 변경 파일
- `.github/workflows/report-file-lint.yml`
- `.github/workflows/report-governance.yml`
- `.github/pull_request_template.md`
- `develop_report/2026-02-23_issue213_lint_governance_screenshot_probe.png`

## 5) 증빙
- `data/verification/issue213_workflow_logic_check.log`
- (PR checks green 후 추가)
