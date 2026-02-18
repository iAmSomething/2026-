---
name: Develop Task
about: 개발 담당 작업 생성
title: "[Develop] "
labels: ["role/develop", "type/task", "status/backlog"]
assignees: []
---

## Goal
-

## Scope
-

## Contract References
- docs/02_DATA_MODEL_AND_NORMALIZATION.md
- docs/03_UI_UX_SPEC.md
- docs/04_DEPLOYMENT_AND_ENVIRONMENT.md
- docs/10_WORKSPACE_LOCK_POLICY.md

## Workspace Lock Checklist
- [ ] 본 작업은 Develop 작업영역(`app/**`, `db/**`, `develop_report/**`, `scripts/qa/**`) 안에서만 수행
- [ ] 공용 잠금 경로(`docs/**`, `.github/**`, `scripts/pm/**`, `README.md`) 수정 시 PM 승인 코멘트 링크 첨부
- [ ] 충돌 가능 파일은 이슈 코멘트로 선점 선언 완료

## Deliverables
- [ ] develop_report/YYYY-MM-DD_<topic>_report.md

## DoD
- [ ] API/DB/CLI 변경 반영
- [ ] 테스트 통과 또는 실패 사유 명시
- [ ] 운영/보안 영향 명시
- [ ] QA PASS 코멘트 확인 후 Done 처리

## Report-Path
`develop_report/YYYY-MM-DD_<topic>_report.md`
