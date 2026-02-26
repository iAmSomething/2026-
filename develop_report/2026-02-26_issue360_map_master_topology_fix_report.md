# 2026-02-26 Issue360 Map Master Topology Fix Report

## 1) 배경
- 지도 우측 `연결 선거`가 응답 원본을 그대로 노출해 `office_type` 중복, 랜덤 코드칩, placeholder 상태 불일치가 발생할 수 있는 구조였습니다.
- 목표: 지도 패널을 공식 master elections 규칙으로 고정하고, 광역 3종 슬롯을 항상 일관되게 노출.

## 2) 수정 내용

### A. 지도 패널 API 호출을 official topology로 고정
- 파일: `apps/web/app/_components/RegionalMapPanel.js`
- 변경:
  - `/api/v1/regions/{region_code}/elections` 호출에 `?topology=official`를 명시적으로 강제

### B. office_type 1대표 슬롯 규칙 적용 (중복 제거)
- 파일: `apps/web/app/_components/RegionalMapPanel.js`
- 변경:
  - `OFFICIAL_SIDO_OFFICES = [광역자치단체장, 광역의회, 교육감]` 고정 슬롯 정의
  - 응답 배열을 `office_type`별 대표 1건으로 정규화
  - 우선순위: `topology=official` > `source=master/code_master` > fallback/placeholder 여부 > poll/candidate data > 최신일자

### C. 광역 3종 placeholder 강제 + 상태카피 일관화
- 파일: `apps/web/app/_components/RegionalMapPanel.js`
- 변경:
  - 누락 슬롯은 placeholder를 생성해 3종 고정 노출
  - `has_poll_data=false`일 때 상태 문자열을 `조사 데이터 없음`으로 일관화
  - 세종(`29-000`) fallback 라벨은 `세종시장/세종시의회/세종교육감`으로 고정

### D. 랜덤 코드칩 제거 및 렌더 규칙 통일
- 파일: `apps/web/app/_components/RegionalMapPanel.js`
- 변경:
  - 우측 하단 region code chip grid 제거
  - 연결 선거 행 렌더를 `office_type + title + status` 통일 규칙으로 고정
  - placeholder는 링크 비활성, 실매치업은 `latest_matchup_id` 우선 링크

## 3) 검증

### 빌드 검증
- 명령:
  - `npm --prefix apps/web run build`
- 결과:
  - `Compiled successfully`

### API 수용 기준 증빙
- 세종 API (`29-000`):
  - `광역자치단체장\t세종시장`
  - `광역의회\t세종시의회`
  - `교육감\t세종교육감`
- 강원 API (`42-000`):
  - `광역자치단체장\t강원특별자치도 광역자치단체장`
  - `광역의회\t강원특별자치도 광역의회`
  - `교육감\t강원특별자치도 교육감`
- `office_type` 중복 카운트:
  - 세종: `0`
  - 강원: `0`

### 첨부 아티팩트
- API raw:
  - `develop_report/assets/issue360/sejong_elections_official.json`
  - `develop_report/assets/issue360/gangwon_elections_official.json`
- API 요약:
  - `develop_report/assets/issue360/sejong_elections_summary.tsv`
  - `develop_report/assets/issue360/gangwon_elections_summary.tsv`
- 중복 카운트:
  - `develop_report/assets/issue360/sejong_duplicate_office_type_count.txt`
  - `develop_report/assets/issue360/gangwon_duplicate_office_type_count.txt`
- 웹 캡처:
  - `develop_report/assets/issue360/web_sejong_selected_region.png`
  - `develop_report/assets/issue360/web_gangwon_selected_region.png`

## 4) 반영 파일
- `apps/web/app/_components/RegionalMapPanel.js`

## 5) 의사결정 필요 사항
1. 지도 우측 `연결 선거` 슬롯 범위 고정안
- 현재는 광역 3종만 고정 노출(재보궐 등 추가 office_type 미노출)
- 결정 필요: 지도 패널에서 추가 office_type(예: `재보궐`)을 함께 노출할지 여부
