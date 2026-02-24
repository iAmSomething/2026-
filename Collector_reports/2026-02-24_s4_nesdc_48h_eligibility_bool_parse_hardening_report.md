# [COLLECTOR][S4] NESDC 48h eligibility 불리언 파싱 엄격화 보고서 (#236)

## 1) 목표
- `auto_collect_eligible_48h` 불리언 판정의 문자열 오해석(`'false'`, `'0'`) 제거
- 미지원 값은 수집 제외 + `review_queue(mapping_error)` 라우팅
- 48h 안전윈도우 우회 방지 가드 추가

## 2) 구현 내용
1. 명시적 불리언 파서 도입
- 파일: `scripts/generate_nesdc_safe_collect_v1.py`
- 허용 입력: `true/false`, `1/0`, `yes/no`, 실제 `bool`
- 미지원 입력은 `None` 처리

2. eligibility 결정 흐름 분리
- 등록시각 기반 48h 판정 함수 분리: `_is_registered_at_eligible`
- `auto_collect_eligible_48h`가 있을 때:
  - 파싱 실패: `mapping_error` + `INVALID_AUTO_COLLECT_ELIGIBLE_48H` + row skip
  - `false`: 비수집 처리
  - `true` + 48h 미충족: `mapping_error` + `SAFE_WINDOW_GUARD_BLOCKED` + row skip

3. 리포트 카운트 보강
- `eligibility_parse_error_count`
- `safe_window_guard_block_count`
- `fallback_review_queue_synced`는 추가 라우팅 건을 포함해 일관성 검증

## 3) 테스트
- 수정: `tests/test_nesdc_safe_collect_v1_script.py`
- 추가 케이스:
  - `'false'`, `'0'`, `false` 모두 비수집 처리
  - 미지원 문자열(`"maybe"`)은 `mapping_error` 라우팅 + skip
  - `true`라도 48h 미충족이면 guard로 차단 + `mapping_error`

실행:
```bash
PYTHONPATH=. /Users/gimtaehun/election2026_codex/.venv/bin/pytest -q \
  tests/test_nesdc_safe_collect_v1_script.py \
  tests/test_nesdc_live_v1_pack_script.py
```
결과: `8 passed`

## 4) 완료 기준 충족 여부
- `'false'`, `'0'`, `false` 입력 비수집: 충족
- 미지원 문자열 입력 시 skip + review_queue 생성: 충족
- 회귀 테스트 추가/통과: 충족

## 5) 의사결정 필요사항
- 없음
