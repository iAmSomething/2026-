# 2026-02-26 DEVELOP 한반도 형상 지도(ADM1) 교체 보고서 (#275)

## 1) 작업 개요
1. 대상 파일: `apps/web/public/geo/kr_adm1_simplified.geojson`
2. 기존 문제: 사각형 placeholder 폴리곤(11개)로 한반도 형상 불일치
3. 조치: 실제 ADM1 경계(17개 시도) GeoJSON으로 교체

## 2) 데이터 소스
1. source: `southkorea/southkorea-maps`
2. file: `kostat/2013/json/skorea_provinces_geo_simple.json`
3. 변환: `properties.code` -> `region_code=KR-xx`, `properties.name` -> `region_name`

## 3) 결과
1. feature 수: 11 -> 17
2. region_code: `KR-11, KR-21, ... KR-39` 전체 시도 코드 반영
3. geometry 복잡도(point count) 회귀 테스트 기준 `> 500` 충족

## 4) before / after 시각 비교
- Before:
![before](assets/issue275_map_before.png)
- After:
![after](assets/issue275_map_after.png)

## 5) 검증
1. 실행:
```bash
SUPABASE_URL=https://example.supabase.co \
SUPABASE_SERVICE_ROLE_KEY=test \
DATA_GO_KR_KEY=test \
DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/app \
/Users/gimtaehun/election2026_codex/.venv/bin/pytest
```
2. 결과: `160 passed`
3. 신규 회귀 테스트:
- `tests/test_web_geojson_shape.py`
- 검증 항목: 17개 시도 코드/geometry 복잡도

## 6) 참고
1. 기존 `region_code(KR-11, KR-26...)` 매핑 구조는 유지되어 map-latest 상호작용 호환성 유지.
