# 2026-02-26 issue352 runtime sync reopen fix report

## 1. 배경
- 이슈: #352 (reopen)
- 재오픈 원인: 운영 URL에서 매치업 상세 `h1`이 기사형 제목으로 노출됨.
- 기존 반영(PR #356): `canonical_title/article_title` 필드 추가 및 page.js 렌더링 반영.
- 잔존 문제: `canonical_title` 생성이 `matchups.title` 오염 데이터에 종속되어 canonical이 기사형 문자열로 남음.

## 2. 재현 증거 (reopen 시점)
1. 운영 웹 `h1` 확인
- `/matchups/m_2026_seoul_mayor` -> `<h1>전국지표조사(NBS) 2026-02-26`
- `/matchups/2026_local|기초자치단체장|28-450` -> `<h1>[여론조사] 인천시장 양자대결 ...`

2. 운영 API 확인
- `GET /api/v1/matchups/m_2026_seoul_mayor`
  - `title`: `전국지표조사(NBS) 2026-02-26`
  - `canonical_title`: `전국지표조사(NBS) 2026-02-26`
  - `article_title`: `null`

## 3. 이번 수정
1. `app/services/repository.py`
- `get_matchup()` canonical 제목 산출 로직 교체:
  - 기존: `matchups.title` 우선(오염 시 그대로 전파)
  - 변경: `regions(region_code)` + `office_type` 기반 canonical 생성
- 추가 메서드:
  - `_strip_region_suffix`
  - `_derive_matchup_title_from_region`
  - `_fetch_region_for_matchup_title`
- 결과: `matchups.title`가 기사형이어도 canonical 제목이 지역+선거유형 규칙으로 복원됨.

2. 테스트 보강
- `tests/test_repository_matchup_legal_metadata.py`
  - 오염된 meta/observation title 입력에서도 canonical이 `서울시장`으로 복원되는지 검증.
- `tests/test_repository_matchup_scenarios.py`
  - 신규 region 조회 쿼리 순서를 반영하도록 fixture cursor step 보정.

## 4. 검증
1. 명령
```bash
source .venv313/bin/activate && pytest tests/test_repository_matchup_legal_metadata.py tests/test_repository_matchup_scenarios.py tests/test_api_routes.py
```

2. 결과
- `28 passed`

## 5. 남은 운영 확인
- main 반영 후 아래 2개 URL에서 증빙 채취 필요:
  1. `h1`이 canonical 제목인지
  2. `기사 제목: ...` 부제 라인이 함께 노출되는지
