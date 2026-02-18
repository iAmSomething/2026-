---
name: QA Task
about: QA 담당 작업 생성
title: "[QA] "
labels: ["role/qa", "type/task", "status/backlog"]
assignees: []
---

## Goal
-

## Scope
-

## Contract References
- docs/09_QA_TRACK_OPERATIONS.md
- docs/10_WORKSPACE_LOCK_POLICY.md

## Workspace Lock Checklist
- [ ] 본 작업은 QA 작업영역(`QA_reports/**`, `tests/**`, `scripts/qa/**`) 안에서만 수행
- [ ] 공용 잠금 경로(`docs/**`, `.github/**`, `scripts/pm/**`, `README.md`) 수정 시 PM 승인 코멘트 링크 첨부
- [ ] 충돌 가능 파일은 이슈 코멘트로 선점 선언 완료

## Deliverables
- [ ] QA_reports/YYYY-MM-DD_qa_<topic>_report.md

## DoD
- [ ] 결과 검증(PASS/WARN/FAIL) 및 근거 로그 정리
- [ ] 실패 원인 진단(근거 파일/라인 포함)
- [ ] 재현 시나리오 명시
- [ ] 담당자 재할당 제안 포함

## Report-Path
`QA_reports/YYYY-MM-DD_qa_<topic>_report.md`
