# 2026-02-26 DEVELOP P0 지역 인터랙션 마스터 슬롯 상시 노출 보고서 (#301)

## 1) 작업 범위
1. `/api/v1/regions/{region_code}/elections`를 관측치 의존에서 region master 기반으로 전환
2. 선거 항목별 optional poll 메타 결합
3. 검색 UI에서 상태/준비중 표시 반영

## 2) 핵심 변경
1. Region Elections API 계약 확장
   - `has_poll_data`
   - `has_candidate_data`
   - `latest_survey_end_date`
   - `latest_matchup_id`
   - `status` (`조사 데이터 없음` | `후보 정보 준비중` | `데이터 준비 완료`)
   - `is_placeholder`
2. repository `fetch_region_elections` 재구현
   - `regions` 테이블 기준으로 admin_level별 기본 슬롯 구성
   - `sido`: `광역자치단체장`, `광역의회`, `교육감`
   - `sigungu/local`: 기본 슬롯 + `기초자치단체장`, `기초의회`
   - `재보궐`은 실제 데이터 존재 시 추가
   - `poll_observations` 최신값과 `poll_options(candidate_matchup)` 존재 여부로 상태 산출
3. placeholder title 규칙 추가
   - 예: `강원특별자치도` 기준 `강원도지사 / 강원도의회 / 강원교육감`
4. 검색 페이지 렌더 보강
   - 상태 문자열 및 최신 조사일 노출
   - `latest_matchup_id`가 없는 placeholder는 `매치업 준비중`으로 비활성 렌더

## 3) 변경 파일
1. `/Users/gimtaehun/election2026_codex/app/models/schemas.py`
2. `/Users/gimtaehun/election2026_codex/app/services/repository.py`
3. `/Users/gimtaehun/election2026_codex/apps/web/app/search/page.js`
4. `/Users/gimtaehun/election2026_codex/tests/test_api_routes.py`
5. `/Users/gimtaehun/election2026_codex/tests/test_repository_region_elections_master.py` (신규)

## 4) 검증
1. 부분 검증:
```bash
/Users/gimtaehun/election2026_codex/.venv/bin/python -m pytest -q tests/test_repository_region_elections_master.py tests/test_api_routes.py
```
2. 전체 회귀:
```bash
/Users/gimtaehun/election2026_codex/.venv/bin/python -m pytest -q
```
3. 결과: `177 passed in 7.72s`

## 5) 수용 기준 대비
1. 강원도 선택 시 최소 3개 슬롯 노출: 완료(테스트로 `광역자치단체장/광역의회/교육감` 고정 검증)
2. `poll_observations=0`이어도 elections 비어있지 않음: 완료(master 슬롯 반환)
3. 기존 빈 상태 정책 유지: 완료(`status`/placeholder로 분리)

## 6) 의사결정 필요
1. placeholder 제목 규칙 표준화 필요
   - 현재는 규칙 기반 자동 생성(예: `강원도지사`, `중구청장`)
   - UIUX에서 최종 카피/표기 사전 고정 여부 결정 필요
2. placeholder 항목 클릭 허용 정책 확정 필요
   - 현재는 `latest_matchup_id` 없으면 비활성 처리(`매치업 준비중`)
