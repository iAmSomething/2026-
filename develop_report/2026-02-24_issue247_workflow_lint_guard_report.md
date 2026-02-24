# [DEVELOP] #247 GitHub Actions workflow lint guard 도입 보고서

- 작성일: 2026-02-24
- 담당: role/develop
- 이슈: https://github.com/iAmSomething/2026-/issues/247
- 브랜치: `codex/issue247-workflow-lint-guard`

## 1) 반영 변경
1. CI 가드 워크플로 추가
- 파일: `.github/workflows/workflow-lint-guard.yml`
- 트리거: PR에서 `.github/workflows/*.yml|*.yaml` 변경 시
- 검사:
  - `bash scripts/qa/validate_workflow_yaml.sh`
  - `rhysd/actionlint@v1`

2. 로컬/CI 공통 YAML 파싱 스크립트 추가
- 파일: `scripts/qa/validate_workflow_yaml.sh`
- 동작: `.github/workflows/*.{yml,yaml}` 전체를 Ruby YAML 파서로 검증, 실패 시 즉시 exit 1

3. 운영 가이드 업데이트
- `README.md` QA 섹션에 가드 명령/워크플로 추가
- `docs/05_RUNBOOK_AND_OPERATIONS.md`에 PR fail-fast 절차(정상/깨진 샘플 재현) 추가

## 2) 완료 기준 검증
1. 의도적 깨진 샘플에서 fail 재현
- 임시 파일: `.github/workflows/_tmp_intentional_broken.yml`
- 결과: `fail_code=1`
- 에러: `could not find expected ':' while scanning a simple key`

2. 정상 워크플로 pass
- 임시 파일 제거 후 재실행
- 결과: `.github/workflows/*.yml` 전체 파싱 성공

3. 문서 업데이트
- 운영 가이드/README 반영 완료

## 3) 의사결정 필요 사항
1. 없음
