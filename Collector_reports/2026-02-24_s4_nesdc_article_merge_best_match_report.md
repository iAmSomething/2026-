# [COLLECTOR][S4] NESDC-기사 병합 best-match 선택 로직 보고서 (#237)

## 1) 목표
- NESDC↔기사 병합에서 첫 후보 고정(`article_candidates[0]`) 의존 제거
- 후보군 전체를 스코어링해 best-match 선택
- 동점/저신뢰는 `conflict_review`로 라우팅
- merge evidence에 선택 근거 필드 포함

## 2) 구현 내용
1. 후보 스코어링 함수 추가
- 파일: `scripts/generate_nesdc_live_v1_pack.py`
- 함수: `_score_article_candidate`
- 우선순위(score key):
  - `survey_date exact` 우선
  - `sample_size diff` 최소
  - `margin diff` 최소

2. 병합 로직 개선
- `article_candidates` 전체를 score 정렬 후 최적 후보 선택
- `tie_with_next`/`low_confidence` 계산
- 판정 규칙:
  - `merge_exact`: exact + 동점 아님 + 저신뢰 아님
  - 그 외 `conflict_review`
- `selection_basis`(score key/동점/신뢰도/후보수)를
  - merge evidence decision
  - review_queue payload
  모두에 기록

## 3) 테스트
- 파일: `tests/test_nesdc_live_v1_pack_script.py`
- 추가 케이스:
  - 첫 후보가 오답이어도 두 번째 정확 후보를 선택해 `merge_exact`
  - 동점 후보는 `conflict_review`로 라우팅 + 근거 필드 검증

실행:
```bash
PYTHONPATH=. /Users/gimtaehun/election2026_codex/.venv/bin/pytest -q \
  tests/test_nesdc_live_v1_pack_script.py \
  tests/test_nesdc_safe_collect_v1_script.py
```
결과: `10 passed`

## 4) 완료 기준 충족 여부
- 기존 테스트 유지 + 다중 후보 케이스 테스트 추가: 충족
- 판정이 첫 원소 의존 없이 재현 가능: 충족
- merge evidence 선택 근거 포함: 충족

## 5) 의사결정 필요사항
- 없음
