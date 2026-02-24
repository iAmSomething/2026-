# [DEVELOP] #245 collector-live-news-schedule YAML 파싱 오류 복구 보고서

- 작성일: 2026-02-24
- 담당: role/develop
- 이슈: https://github.com/iAmSomething/2026-/issues/245
- 브랜치: `codex/issue245-workflow-yaml-fix`

## 1) 작업 배경
- 증상: `.github/workflows/collector-live-news-schedule.yml` 파싱 실패 (`could not find expected ':' while scanning a simple key`)
- 원인: `run: |` 블록 내 heredoc 본문 들여쓰기 불일치

## 2) 반영 변경
1. YAML block scalar 규칙에 맞게 heredoc 본문 들여쓰기 정렬
2. `Build live news payload` 단계에서 `PYTHONPATH=.` 명시하여 `src` import 실패 방지
3. `Run ingest with retry` 단계 timeout 파라미터 조정
- `--timeout 180`
- `--timeout-scale-on-timeout 1.5`
- `--timeout-max 360`

## 3) 검증 결과
1. 정적 파싱
- 실행: `ruby -e "require 'yaml'; YAML.load_file('.github/workflows/collector-live-news-schedule.yml')"`
- 결과: pass

2. workflow_dispatch 수동 실행
- 실패(이전): `22338104431` (원인: `ModuleNotFoundError: No module named 'src'`)
- 실패(중간): `22338155800` (원인: ingest retry timeout)
- 성공(최종): `22338262595` (결과: `completed success`)

3. 완료 기준 점검
- `collector-live-news-schedule` 최근 1회 이상 success: 충족 (`22338262595`)
- jobs/steps 생성 및 로그 확인 가능: 충족
- 보고서 제출(`develop_report/`): 충족

## 4) 의사결정 필요 사항
1. ingest timeout 정책 고정 여부
- 현재는 스케줄 안정화를 위해 timeout 상향(180/360) 적용
- 운영 비용/지연 기준에 맞는 표준값 확정 필요
