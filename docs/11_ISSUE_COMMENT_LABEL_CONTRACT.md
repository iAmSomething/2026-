# 이슈 코멘트/라벨 계약 (Automation Contract)

목적
- PM Cycle 자동화가 오판 없이 동작하도록 이슈 라벨/코멘트 형식을 고정한다.

적용 범위
- 저장소 전체 이슈(특히 자동화 대상: PM/DEVELOP/COLLECTOR/UIUX/QA).

## 1) 라벨 계약 (Cardinality = 1)
열린 이슈/닫힌 이슈 모두 아래 4개 축을 정확히 1개씩 가진다.
- 역할: `role/uiux | role/collector | role/develop | role/qa`
- 상태: `status/ready | status/in-progress | status/in-review | status/in-qa | status/blocked | status/done`
- 우선순위: `priority/p0 | priority/p1 | priority/p2`
- 유형: `type/task | type/bug | type/chore`

추가 규칙
- `state=open`인데 `status/done`이면 위반.
- `state=closed`면 `status/done` 필수.
- `state=closed` + `status/done`이면 코멘트에 `[QA PASS]` 필수.

## 2) 상태 전이 규칙
기본 전이
- `status/ready -> status/in-progress -> status/in-review -> status/in-qa -> status/done`

예외
- 외부 의존이 있을 때만 `status/blocked` 사용.
- 차단 해소 시 즉시 원래 흐름으로 복귀.

## 3) 코멘트 계약 (Machine-Readable)
아래 코멘트는 키-값 라인을 반드시 포함한다.

PM 지시 코멘트 (`[PM ...]`)
- 필수 키: `decision:`, `next_status:`

개발 완료 코멘트 (`[DEVELOP 완료 보고]`)
- 필수 키: `report_path:`, `evidence:`, `next_status:`

QA 판정 코멘트 (`[QA PASS]` 또는 `[QA FAIL]`)
- 필수 키: `report_path:`, `evidence:`, `next_status:`

자동 코멘트
- 자동화 봇 코멘트는 `auto_key:`를 사용해 중복 게시를 방지한다.

## 4) 권장 템플릿
- `docs/templates/comments/PM_COMMAND_TEMPLATE.md`
- `docs/templates/comments/DEVELOP_COMPLETE_TEMPLATE.md`
- `docs/templates/comments/QA_RESULT_TEMPLATE.md`

## 5) CI 검증
워크플로
- `.github/workflows/issue-contract-guard.yml`

검증 이벤트
- `issues` 이벤트: 라벨 cardinality / closed+done+QA PASS 검증
- `issue_comment` 이벤트: 필수 키(`decision/report_path/evidence/next_status`) 검증

운영 원칙
- 검증 실패 시 Action은 실패한다.
- 실패 시 이슈에 `[CONTRACT FAIL]` 안내 코멘트를 자동 남긴다(중복 방지 키 포함).
