# 2026-02-26 DEVELOP P0 회귀 복구/운영정책 반영 보고서 (#270, #271, #273)

## 1) 범위
1. #270 `[DEVELOP][P0] 매치업 404 회귀 복구`
2. #271 `[DEVELOP][P0] 대시보드 fixture fallback 차단`
3. #273 `[DEVELOP+COLLECTOR][P0] regions/search 전체 선거구 검색 보장`

## 2) 구현 요약
1. 매치업 API를 `matchups` 메타 우선 조회로 변경.
2. 관측치 없는 매치업도 `200` 반환 + `has_data=false`, `options=[]` 계약 추가.
3. 매치업 ID 정규화 강화(인코딩/region code 정규화) + 저장된 canonical 매치업 fallback 조회.
4. 대시보드 summary 응답 루트에 `data_source(official|article|mixed)` 추가.
5. 웹 대시보드에 `data_source` 배지 노출.
6. 웹 summary API 실패 시 fallback 정책 분리:
   - production/preview: fallback 금지(오류 상태 유지)
   - local/dev/test: fixture fallback 허용
7. 지역검색 API에 `has_data`, `matchup_count` 보조 필드 추가.
8. CommonCodeService 기반 `regions` full seed 실행 경로 신규 추가:
   - `app/services/data_go_common_codes.py`
   - `scripts/sync_common_codes.py`

## 3) 변경 파일
1. `app/services/repository.py`
2. `app/api/routes.py`
3. `app/models/schemas.py`
4. `apps/web/app/page.js`
5. `apps/web/app/_lib/api.js`
6. `apps/web/app/matchups/[matchup_id]/page.js`
7. `scripts/sync_common_codes.py`
8. `app/services/data_go_common_codes.py`
9. `tests/test_api_routes.py`
10. `tests/test_sync_common_codes.py`
11. `docs/02_DATA_MODEL_AND_NORMALIZATION.md`
12. `docs/03_UI_UX_SPEC.md`

## 4) 검증 결과
1. 실행 명령:
```bash
SUPABASE_URL=https://example.supabase.co \
SUPABASE_SERVICE_ROLE_KEY=test \
DATA_GO_KR_KEY=test \
DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/app \
/Users/gimtaehun/election2026_codex/.venv/bin/pytest tests/test_api_routes.py tests/test_sync_common_codes.py
```
2. 결과: `14 passed`.
3. 문법검사:
```bash
python3 -m py_compile app/services/data_go_common_codes.py scripts/sync_common_codes.py app/api/routes.py app/services/repository.py
```
4. 결과: 성공.

## 5) 완료 기준 대비
1. #270 재현 ID 케이스: API 계약상 404 대신 200(empty payload) 경로 구현 완료.
2. #270 UI empty-state: "데이터 준비 중" 메시지 반영 완료.
3. #271 production fallback 차단/로컬 허용: 환경 기반 정책 분리 완료.
4. #271 source 배지: summary `data_source` 기반 배지 노출 완료.
5. #273 데이터 유무와 무관한 검색: `regions` 테이블 기준 검색 + `has_data`/`matchup_count` 노출 완료.
6. #273 full seed 실행 경로: CommonCodeService sync 스크립트 구현 완료.

## 6) 남은 운영 실행(오너/운영)
1. 실제 CommonCodeService endpoint URL 확정 후 아래 1회 실행 필요:
```bash
PYTHONPATH=. .venv/bin/python scripts/sync_common_codes.py \
  --region-url "$COMMON_CODE_REGION_URL" \
  --region-sigungu-url "$COMMON_CODE_SIGUNGU_URL"
```
2. 실행 후 `data/common_codes_sync_report.json` 산출물로 건수 확인.

## 7) 의사결정 필요 사항
1. `COMMON_CODE_SIGUNGU_URL`를 별도 엔드포인트로 분리할지, 단일 endpoint로 통합 응답을 받을지 확정 필요.
2. 운영에서 `regions` 동기화 주기(수동 1회/일배치)를 확정 필요.
