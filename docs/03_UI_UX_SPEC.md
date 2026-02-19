# UI/UX 화면 명세

- 문서 버전: v0.2
- 최종 수정일: 2026-02-19
- 수정자: Codex

## 1. 디자인 원칙
1. 톤: 데이터 뉴스룸형
2. 우선 디바이스: 데스크탑
3. 모바일: 핵심 카드 중심 축약 레이아웃
4. 원칙: 수치 + 근거 + 출처를 함께 노출

## 2. 정보 구조(IA)
1. 메인 대시보드
2. 지역 검색 결과(기초자치단체 중심)
3. 매치업 상세
4. 후보자 상세

## 3. 화면별 요구사항

## 3.1 메인 대시보드
### 컴포넌트
1. 최신 정당 여론조사 요약 카드
2. 대통령 지지율 요약 카드
3. 광역 단위 한반도 지도(Hover)
4. 이 주의 빅매치 2~3개

### 동작
1. 지도 Hover 시 해당 지역 최신 매치업(광역단체장/교육감) 툴팁 표시
2. 빅매치 카드 클릭 시 매치업 상세 이동

## 3.2 검색
### 요구
1. 기초자치단체 검색(예: 인천 연수구, 경기 시흥시)
2. 자동완성/오타 허용
3. 선거 타입 탭 6종 제공

### 선거 타입
1. 광역자치단체장
2. 광역의회
3. 교육감
4. 기초자치단체장
5. 기초의회
6. 재보궐(존재 시)

## 3.3 매치업 상세
1. 후보별 추세선(시계열)
2. 최근 조사 카드(기관/표본/오차범위/조사기간)
3. 출처 링크 및 검증 상태 배지
4. 후보 클릭 시 후보자 상세 이동

## 3.4 후보자 상세
1. 후보 기본 정보(성명/정당/연령대/직업)
2. 약력 및 출마 정보
3. 관련 매치업 요약

## 4. 화면-데이터 1:1 매핑

| 화면 기능 | 사용 API | 핵심 테이블 | 필수 필드 |
|---|---|---|---|
| 최신 정당/대통령 요약 | `GET /api/v1/dashboard/summary` | `poll_observations`, `poll_options` | `pollster`, `survey_end_date`, `option_name`, `value_mid`, `verified`, `audience_scope`(national only), `source_channel`, `source_channels` |
| 지도 Hover 최신값 | `GET /api/v1/dashboard/map-latest` | `regions`, `matchups`, `poll_options` | `region_code`, `office_type`, `title`, `value_mid`, `source_channel`, `source_channels` |
| 빅매치 카드 | `GET /api/v1/dashboard/big-matches` | `matchups`, `poll_observations` | `matchup_id`, `title`, `survey_end_date`, `value_mid`, `source_channel`, `source_channels` |
| 지역 검색 | `GET /api/v1/regions/search` | `regions` | `region_code`, `sido_name`, `sigungu_name` |
| 지역별 선거 탭 | `GET /api/v1/regions/{region_code}/elections` | `matchups` | `region_code`, `office_type`, `is_active` |
| 매치업 상세 | `GET /api/v1/matchups/{matchup_id}` | `poll_observations`, `poll_options` | `matchup_id`, `pollster`, `survey_start_date`, `survey_end_date`, `confidence_level`, `sample_size`, `response_rate`, `margin_of_error`, `date_inference_mode`, `date_inference_confidence`, `value_mid`, `source_grade`, `audience_scope`, `audience_region_code`, `legal_completeness_score`, `legal_filled_count`, `legal_required_count`, `source_channel`, `source_channels`, `poll_fingerprint` |
| 후보자 상세 | `GET /api/v1/candidates/{candidate_id}` | `candidates`, `candidate_profiles` | `candidate_id`, `name_ko`, `party_name`, `career_summary` |

## 5. API-UI 필드명 일치 규칙
1. UI에서 수치표시는 항상 `value_mid` 기준
2. 원문 표시 필요 시 `value_raw` 보조 표기
3. 검증 배지는 `verified` 또는 `source_grade` 기준
4. 지역 선택의 기준 키는 `region_code` 단일 사용
5. 대시보드 요약 카드는 `audience_scope='national'`로 스코프 분리된 데이터만 사용
6. 매치업 상세는 조사 스코프(`audience_scope`)와 법정 completeness(`legal_*`)를 함께 노출
7. 대시보드 계열 API의 `source_channels`는 null 대신 빈 배열(`[]`)을 기본값으로 노출
8. 매치업 상세의 법정메타 결측값은 `null`로 유지한다(숫자/날짜 모두 동일)
