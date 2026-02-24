# [COLLECTOR][S4] NESDC live pack 기사 payload 의존성 제거(옵셔널화) 보고서 (#238)

## 1) 목표
- NESDC live pack이 기사 payload 파일 미존재로 실패하지 않도록 옵셔널 처리
- 미존재 시 빈 fingerprint로 degrade 동작
- 실행 컨텍스트를 리포트에 명시

## 2) 구현 내용
1. optional payload 로더 추가
- 파일: `scripts/generate_nesdc_live_v1_pack.py`
- 함수: `_load_optional_article_payload`
- 동작:
  - 파일 존재: 기존처럼 JSON 로드
  - 파일 미존재: `{"records": []}` + `article_payload_present=false`

2. 리포트 컨텍스트 필드 추가
- `report.source.article_payload_present`
- `report.source.article_fingerprint_count`
- `report.source.article_pollster_count`

3. 병합 정책 degrade 보장
- 파일 미존재 시 `article_fp` 빈 맵으로 생성
- merge policy는 `insert_new` 중심으로 정상 진행

## 3) 테스트
- 파일: `tests/test_nesdc_live_v1_pack_script.py`
- 추가 케이스: `test_nesdc_live_pack_without_article_payload_file`
  - payload 파일 없이 실행해도 예외 없음
  - `article_payload_present=false`
  - `article_fingerprint_count=0`
  - `insert_new`로 정상 판정

실행:
```bash
PYTHONPATH=. /Users/gimtaehun/election2026_codex/.venv/bin/pytest -q \
  tests/test_nesdc_live_v1_pack_script.py \
  tests/test_nesdc_safe_collect_v1_script.py
```
결과: `11 passed`

## 4) 완료 기준 충족 여부
- 기사 payload 파일 미존재 시 정상 완료: 충족
- 병합 정책이 실패 없이 `insert_new` 중심 동작: 충족
- 테스트에 파일 없음 케이스 추가: 충족

## 5) 의사결정 필요사항
- 없음
