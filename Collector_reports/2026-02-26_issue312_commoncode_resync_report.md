# 2026-02-26 Issue #312 CommonCodeService 전수 재동기화 보고서

## 1) 이슈
- Issue: #312 `[COLLECTOR][P0] CommonCodeService 전수 재동기화(운영 DB): 시도/시군구 누락 0`
- 목표:
  - regions 카디널리티 복구(시도/시군구 누락 0)
  - 강원 샘플 조회 증빙(광역 + 시군구)
  - sync 전/후 비교 JSON
  - elections master 슬롯 동기화 실행
  - #314 fallback 전/후 비교 케이스 포함

## 2) 실행 요약
- 운영 DB pre snapshot:
  - `regions_by_level`: `sido=6`, `sigungu=26`
  - `42-000` 미존재
  - `elections`는 master 컬럼 미구성 상태(`region_code/office_type` 없음)
- CommonCodeService(`sgId=20260603`) 전수 수집:
  - 시도 17건(`sgTypecode=3`)
  - 시군구 227건(`sgTypecode=4`, page 순회)
- 매핑:
  - DB/기존 표준/TSV 보조 lookup으로 코드 해석
  - 최종 unresolved 0
  - 예외(생성 코드) 4건:
    - `28-900` 영종구
    - `28-901` 제물포구
    - `28-902` 검단구
    - `41-900` 화성시만세구
- 동기화 반영:
  - regions upsert 244건
  - elections 스키마 패치 후 master slot sync 실행

## 3) 결과 (완료기준 대조)
1. regions 누락 0 확인
- 충족.
- CommonCodeService 기준 expected 244(17+227) 대비 resolved 244, unresolved 0.

2. 강원 샘플 조회(광역 + 시군구)
- 충족.
- `42-000(강원특별자치도)` + `42-110(춘천시)` 조회 증빙 첨부.

3. sync 전/후 카디널리티 비교
- 충족.
- pre: `sido=6`, `sigungu=26`
- post: `sido=17`, `sigungu=240`
- 운영 regions total: `32 -> 257` (기존 레거시 row 보존 + 신규 반영)

4. elections master sync 실행
- 충족.
- slot_count 533, missing_default_slot_pairs 0.
- 샘플 체크:
  - `42-000` 슬롯 3건
  - `26-710` 슬롯 2건

5. #314 환경 전/후 비교 케이스
- 충족.
- before: master rows empty(`elections_total=0`)라 fallback 경로 필요 상태.
- after: master rows populated(`elections_total=533`)로 primary master 경로 사용 가능.

## 4) 산출물 경로
- 실행 리포트:
  - `data/issue312_sync_report.json`
- pre snapshot:
  - `data/issue312_pre_snapshot.json`
- post snapshot:
  - `data/issue312_post_snapshot.json`
- before/after compare:
  - `data/issue312_sync_before_after.json`
- elections master sync report:
  - `data/elections_master_sync_report_issue312.json`
- 강원/대표 샘플 증빙:
  - `data/issue312_gangwon_sample_evidence.json`
- 실행 스크립트(재현용):
  - `scripts/run_issue312_commoncode_resync.py`

## 5) 의사결정 요청
1. 생성 코드 4건(`28-900/901/902`, `41-900`)의 표준 코드 확정 필요
- 현재는 누락 0 복구를 위한 임시 deterministic 코드로 반영됨.
- 표준 코드 확정 시 재매핑 1회 필요.

2. regions prune 정책 확정 필요
- 이번 실행은 운영 안전성을 위해 기존 row를 삭제하지 않고 upsert만 수행.
- CommonCodeService strict set(244)만 유지할지, legacy row 유지할지 정책 결정 필요.
