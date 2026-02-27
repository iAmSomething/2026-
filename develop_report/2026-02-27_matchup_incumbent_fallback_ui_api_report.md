# 2026-02-27 Matchup Incumbent Fallback UI/API Report

## 1) 작업 개요
- 이슈: #483 `[DEVELOP][P1] 매치업 무데이터 시 현직자 fallback 노출(API/UI)`
- 목적: `GET /api/v1/matchups/{matchup_id}`에서 poll scenario/option이 0건일 때만 현직자 fallback을 API/UI로 제공
- 원칙: poll 데이터가 1건 이상이면 fallback 절대 비노출

## 2) 구현 변경

### 2.1 API 계약 확장
- 파일: `app/models/schemas.py`
- 추가:
  - `IncumbentFallbackCandidateOut`
    - `name`, `party`, `office`, `confidence`, `reasons`, `candidate_id`
  - `MatchupOut.fallback_mode: none|incumbent` (default `none`)
  - `MatchupOut.incumbent_candidates: []` (default empty)

### 2.2 매치업 라우트 fallback 가드
- 파일: `app/api/routes.py`
- 추가:
  - `_matchup_has_poll_payload(payload)`
    - `options` + `scenarios[].options` 존재 여부로 poll 데이터 유무 판정
- 정책 적용:
  - poll payload 0건인 경우에만 `repo.fetch_incumbent_candidates(...)` 호출
  - 후보가 존재하면 `fallback_mode='incumbent'`, `incumbent_candidates` 채움
  - poll payload 1건 이상이면 `fallback_mode='none'`, `incumbent_candidates=[]`

### 2.3 저장소 fallback 후보 추정
- 파일: `app/services/repository.py`
- 추가:
  - `fetch_incumbent_candidates(region_code, office_type, limit=4)`
  - 지역/직책 힌트 토큰 기반 점수화(`office_text_match`, `office_token_match`, `region_keyword_match`)
  - 후보명 noise 토큰 필터 적용
  - 매칭이 없을 때 placeholder 1건 반환:
    - `name='현직자 정보 준비중'`
    - `reasons=['incumbent_context_unavailable']`

### 2.4 UI 전용 fallback 블록
- 파일: `apps/web/app/matchups/[matchup_id]/page.js`
- 변경:
  - `isIncumbentFallback = (fallback_mode==='incumbent' && poll payload 0건)`
  - 전용 섹션 렌더:
    - 배지 `추정(현직 기반)`, `여론조사 아님`
    - `incumbent_candidates` 목록 + 프로필 링크(candidate_id 있을 때만)
  - 시나리오 영역은 fallback 상태에서 poll 카드 대신 안내 문구 노출

- 파일: `apps/web/app/globals.css`
- 추가:
  - `.fallback-panel`, `.fallback-candidate-list`, `.fallback-candidate-item`, `.fallback-candidate-head`

### 2.5 명세 문서 반영
- 파일: `docs/02_DATA_MODEL_AND_NORMALIZATION.md`
  - matchup fallback 규칙 2개 추가
- 파일: `docs/03_UI_UX_SPEC.md`
  - 매치업 상세 fallback UI 정책 추가
  - 매치업 API 필수 필드에 `fallback_mode`, `incumbent_candidates[]` 추가

## 3) 테스트/검증
- 파일: `tests/test_api_routes.py`
- 추가/보강:
  - 기존 matchup 응답 기본값 검증:
    - `fallback_mode == 'none'`
    - `incumbent_candidates == []`
  - 신규 회귀 테스트:
    - poll=0 매치업 -> `fallback_mode='incumbent'`, 후보 목록 노출
    - poll 존재 매치업 -> fallback 비노출 유지

- 실행 명령:
  - `.venv/bin/pytest -q tests/test_api_routes.py -k "matchup or fallback"`
- 결과:
  - `6 passed, 32 deselected, 0 failed`

## 4) 수용 기준 체크
- [x] poll=0 매치업에서만 fallback 노출
- [x] poll 존재 매치업에서 fallback 노출 0건
- [x] UI에 `여론조사 아님` 문구 상시 표기

## 5) 의사결정 필요 사항
1. `fallback 후보 0건`일 때 placeholder(`현직자 정보 준비중`)를 계속 노출할지, 아니면 빈 배열로 둘지 확정 필요
2. `confidence` 표시 형식(정수 % vs 소수점 1자리 %)을 UI 공통 규칙으로 고정 필요
3. fallback 후보 최대 노출 개수(현재 4개) 확정 필요
