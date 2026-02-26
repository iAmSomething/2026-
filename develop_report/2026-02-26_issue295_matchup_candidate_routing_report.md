# 2026-02-26 DEVELOP P1 후보 클릭 라우팅 완성 보고서 (#295)

## 1) 작업 범위
1. 매치업 옵션의 `candidate_id` 응답 키 필수화
2. 매치업 화면 후보명 클릭/`프로필` 버튼 라우팅 추가
3. 후보 상세 진입 시 `from=matchup&matchup_id=...` 복귀 링크 유지

## 2) 핵심 변경
1. API 계약
   - `MatchupOptionOut.candidate_id`를 필수 키(값 `null` 허용)로 조정
   - `candidate_id` 누락 시에도 응답에서 키가 빠지지 않도록 테스트 보강
2. 매치업 UI (`/matchups/[matchup_id]`)
   - 후보명 자체를 후보 상세 링크로 제공
   - `프로필` 버튼 추가
   - `candidate_id` 누락 후보는 `프로필` 버튼 disabled 처리 + `candidate_id 누락` 사유 배지 표시
   - 후보 상세 링크에 `?from=matchup&matchup_id=<canonical_id>` 전달
3. 후보 상세 UI (`/candidates/[candidate_id]`)
   - `from=matchup&matchup_id=...` 파라미터가 있으면 `매치업으로 복귀` 링크 노출

## 3) 변경 파일
1. `/Users/gimtaehun/election2026_codex/app/models/schemas.py`
2. `/Users/gimtaehun/election2026_codex/apps/web/app/matchups/[matchup_id]/page.js`
3. `/Users/gimtaehun/election2026_codex/apps/web/app/candidates/[candidate_id]/page.js`
4. `/Users/gimtaehun/election2026_codex/tests/test_api_routes.py`

## 4) 검증
1. 실행:
```bash
/Users/gimtaehun/election2026_codex/.venv/bin/python -m pytest -q
```
2. 결과: `175 passed in 3.19s`

## 5) 완료 기준 대비
1. 매치업 후보 행마다 후보 상세 이동 가능: 완료
2. `candidate_id` 누락 후보 버튼 비활성 + 사유 뱃지: 완료
3. e2e 스모크: 코드/계약 변경 반영 완료, CI 단계 검증 대상

## 6) 의사결정 필요
1. disabled 상태 문구 표준 확정 필요
   - 현재: `candidate_id 누락`
   - 대안: `후보식별자 미매핑(검수대기)`
