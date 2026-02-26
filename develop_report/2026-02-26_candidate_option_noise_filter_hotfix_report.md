# 2026-02-26 Candidate Option Noise Filter Hotfix Report

## 1) 배경 / 증상
- 사용자 제보: 후보별 최신 지표에 후보명 대신 의미 없는 토큰(`오차는`, `민주`, `같은`, `국힘`, `차이` 등)이 노출됨.
- 영향: `/api/v1/matchups/{matchup_id}` 응답의 `options`, `scenarios` 품질 저하.

## 2) 원인
- `app/services/repository.py`의 `PostgresRepository._normalize_options()`에서 후보 옵션명 품질 검증이 없어, 과거 오염 데이터/누락 검증 데이터가 그대로 응답에 포함됨.
- ingest 단계에도 일부 단어(`민주`, `국힘`, `같은`, `차이`, `외`)가 노이즈 사전에 없어 재유입 가능성이 존재함.

## 3) 수정 사항

### A. 조회 단계 2차 방어(핫픽스)
- 파일: `app/services/repository.py`
- 변경:
  - 후보 옵션 토큰 정규화 함수 추가.
  - 노이즈 판정 함수 추가.
    - exact 차단: `오차는`, `민주`, `국힘`, `차이`, `같은`, `외` 등
    - substring 차단: `오차범위`, `표본오차`, `응답률`, `여론조사`, `지지율` 등
    - 숫자 포함/한글 이름 패턴 불일치 차단
  - `_normalize_options()`에서 노이즈 옵션을 API 응답에서 제외.

### B. ingest 단계 재유입 방지 보강
- 파일: `app/services/ingest_service.py`
- 변경:
  - 노이즈 사전을 `exact`/`contains`로 분리.
  - `민주`, `국힘`, `같은`, `차이`, `외`를 exact 차단에 추가.
  - `_looks_like_noise_candidate()`가 exact/contains를 구분해 판정하도록 수정.

## 4) 테스트

### 추가/수정 테스트
- `tests/test_repository_matchup_scenarios.py`
  - `test_normalize_options_filters_noise_candidate_tokens`
  - 노이즈 토큰 필터링 + 정상 이름(`정원오`, `오세훈`, `김민주`) 유지 검증
- `tests/test_ingest_service.py`
  - `test_candidate_party_alias_token_routes_manual_review_mapping_error`
  - `민주` 토큰 ingest 시 `CANDIDATE_TOKEN_NOISE`로 review_queue 라우팅 검증

### 실행 결과
- 명령: `/Users/gimtaehun/election2026_codex/.venv/bin/python -m pytest -q tests/test_repository_matchup_scenarios.py tests/test_ingest_service.py`
- 결과: `15 passed`

## 5) 기대 효과
- 후보 상세/매치업 화면에서 의미 없는 단어 노출 차단.
- 동일 패턴의 오염 텍스트가 ingest 단계에서 review_queue로 우회되어 재유입 감소.

## 6) 의사결정 필요
1. 기존 오염 데이터 정리 여부
- 옵션 A: 즉시 정리(권장)
  - 과거 오염 옵션을 DB에서 `candidate_verified=false`, `needs_manual_review=true`로 일괄 마킹
  - 장점: 즉시 화면 품질 개선 + 추적 가능
- 옵션 B: 그대로 유지
  - API 필터로 가려지나, 원본 DB 오염 레코드는 잔존

2. 노이즈 토큰 운영 정책
- 옵션 A: 현재 룰 유지(권장)
  - 과차단 리스크 낮음, 빠른 안정화
- 옵션 B: 토큰 확대
  - 민감도는 올라가나 과차단 가능성도 함께 증가

## 7) 반영 대상
- 브랜치: `codex/issue330-candidate-option-noise-filter`
- 주요 파일:
  - `app/services/repository.py`
  - `app/services/ingest_service.py`
  - `tests/test_repository_matchup_scenarios.py`
  - `tests/test_ingest_service.py`
