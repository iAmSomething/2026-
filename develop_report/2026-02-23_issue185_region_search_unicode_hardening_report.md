# 2026-02-23 W3 환경별 비ASCII 질의 편차 제거 보고서 (#185)

## 1) 목적
- `/api/v1/regions/search`에서 환경/클라이언트별 비ASCII 질의 전달 편차(이중 인코딩, NFD 조합형 한글, 전각 공백)로 인해 발생하는 조회 불일치를 제거한다.

## 2) 구현 범위
- API 입력 정규화 하드닝
- 지역 검색 SQL 공백 변형 대응 강화
- 회귀 테스트팩 확장 및 재현 증빙 생성

## 3) 구현 상세
1. API 입력 정규화 추가 (`app/api/routes.py`)
- `_normalize_region_query` 신설
- 처리 규칙:
  - 전각 공백(`\u3000`) -> 일반 공백 변환
  - 최대 2회 percent-decoding (`%25...` 이중 인코딩 입력 대응)
  - Unicode NFC 정규화 (NFD 한글 입력 대응)
  - 다중 공백 1칸으로 압축
- `/api/v1/regions/search`에서 `q/query` 값을 정규화 후 repository에 전달

2. 저장소 검색 하드닝 (`app/services/repository.py`)
- 공백 포함 패턴(`%서울 특별시%`) + 공백 제거 패턴(`%서울특별시%`)을 함께 검색
- `REPLACE(..., ' ', '') ILIKE` 조건 추가로 환경별 공백 전달 편차 대응
- 공백-only 입력은 즉시 빈 결과 반환

3. 테스트 확장
- `tests/test_api_routes.py`
  - 이중 인코딩 질의(`%25EC...`)가 `서울`로 정규화되는지 검증
  - NFD 한글 질의가 `서울`(NFC)로 정규화되는지 검증
  - 전각 공백/여분 공백이 `서울 특별시`로 정규화되는지 검증
- `tests/test_repository_region_search_hardening.py` (신규)
  - SQL에 compact matching 조건이 포함되는지 검증
  - 공백-only 질의 처리 회귀 방지 검증

## 4) 검증 결과
- 명령: `/Users/gimtaehun/election2026_codex/.venv/bin/python -m pytest -q`
- 결과: `93 passed`

## 5) 증빙 파일
- `data/verification/issue185_region_search_hardening_pytest.log`
- `data/verification/issue185_region_search_normalization_sample.json`
- `data/verification/issue185_region_search_hardening_sha256.txt`

## 6) 기대 효과
- 동일 의미의 한글 질의가 입력 경로/클라이언트 인코딩 형태와 무관하게 동일 검색 결과로 수렴한다.
- 운영 중 재현이 어려운 “특정 환경에서만 지역검색 실패” 류 이슈를 테스트로 선제 차단한다.
