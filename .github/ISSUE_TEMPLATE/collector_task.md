---
name: Collector Task
about: 수집기 담당 작업 생성
title: "[Collector] "
labels: ["role/collector", "type/task", "status/backlog"]
assignees: []
---

## Goal
-

## Scope
-

## Contract References
- docs/06_COLLECTOR_CONTRACTS.md
- docs/02_DATA_MODEL_AND_NORMALIZATION.md
- docs/10_WORKSPACE_LOCK_POLICY.md

## Workspace Lock Checklist
- [ ] 본 작업은 Collector 작업영역(`src/pipeline/**`, `Collector_reports/**`, `data/**`) 안에서만 수행
- [ ] 공용 잠금 경로(`docs/**`, `.github/**`, `scripts/pm/**`, `README.md`) 수정 시 PM 승인 코멘트 링크 첨부
- [ ] 충돌 가능 파일은 이슈 코멘트로 선점 선언 완료

## Deliverables
- [ ] Collector_reports/YYYY-MM-DD_<topic>_report.md

## DoD
- [ ] 입력/식별자/정규화/오류 계약 준수
- [ ] 테스트 또는 검증 로그 첨부
- [ ] 백엔드 연동 영향도 명시
- [ ] QA PASS 코멘트 확인 후 Done 처리

## Report-Path
`Collector_reports/YYYY-MM-DD_<topic>_report.md`
