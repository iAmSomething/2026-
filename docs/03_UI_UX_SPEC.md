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
| 최신 정당/대통령 요약 | `GET /api/v1/dashboard/summary` | `poll_observations`, `poll_options` | `pollster`, `survey_end_date`, `option_name`, `value_mid`, `verified`, `audience_scope`(national only), `source_priority`, `selected_source_tier`, `selected_source_channel`, `source_trace`, `selection_trace`, `selected_reason`, `official_release_at`, `article_published_at`, `freshness_hours`, `is_official_confirmed`, `source_channel`, `source_channels`, `selection_policy_version`, `data_source`, `party_support`, `president_job_approval`, `election_frame`, `presidential_approval`(deprecated), `scope_breakdown` |
| 지도 Hover 최신값 | `GET /api/v1/dashboard/map-latest` | `regions`, `matchups`, `poll_options` | `region_code`, `office_type`, `canonical_title`, `article_title`, `title`(deprecated), `value_mid`, `audience_scope`, `source_priority`, `selected_source_tier`, `selected_source_channel`, `source_trace`, `selection_trace`, `official_release_at`, `article_published_at`, `freshness_hours`, `is_official_confirmed`, `source_channel`, `source_channels`, `scope_breakdown` |
| 빅매치 카드 | `GET /api/v1/dashboard/big-matches` | `matchups`, `poll_observations` | `matchup_id`, `canonical_title`, `article_title`, `title`(deprecated), `survey_end_date`, `value_mid`, `audience_scope`, `audience_region_code`, `source_trace`, `source_priority`, `official_release_at`, `article_published_at`, `freshness_hours`, `is_official_confirmed`, `source_channel`, `source_channels`, `scope_breakdown` |
| 운영 품질 패널 | `GET /api/v1/dashboard/quality` | `poll_observations`, `articles`, `review_queue` | `quality_status`, `freshness_p50_hours`, `freshness_p90_hours`, `official_confirmed_ratio`, `needs_manual_review_count`, `freshness.status`, `freshness.over_24h_ratio`, `freshness.over_48h_ratio`, `official_confirmation.confirmed_ratio`, `official_confirmation.unconfirmed_count`, `review_queue.pending_count`, `review_queue.in_progress_count`, `review_queue.pending_over_24h_count`, `source_channel_mix.article_ratio`, `source_channel_mix.nesdc_ratio` |
| 추세선 카드(정당/직무평가/선거성격) | `GET /api/v1/trends/{metric}` | `poll_observations`, `poll_options` | `metric`, `scope`, `region_code`, `days`, `survey_end_date`, `option_name`, `value_mid`, `pollster`, `source_trace.selected_source_tier` |
| 지역 검색 | `GET /api/v1/regions/search` (`q/query` optional, `has_data` optional) | `regions`, `elections` | `region_code`, `sido_name`, `sigungu_name`, `has_data`, `matchup_count` |
| 지역별 선거 탭 | `GET /api/v1/regions/{region_code}/elections` | `matchups` | `region_code`, `office_type`, `is_active` |
| 매치업 상세 | `GET /api/v1/matchups/{matchup_id}` | `matchups`, `poll_observations`, `poll_options`, `review_queue` | `matchup_id`, `canonical_title`, `article_title`, `title`(deprecated), `has_data`, `pollster`, `survey_start_date`, `survey_end_date`, `confidence_level`, `sample_size`, `response_rate`, `margin_of_error`, `date_inference_mode`, `date_inference_confidence`, `nesdc_enriched`, `needs_manual_review`, `source_trace`, `source_priority`, `official_release_at`, `article_published_at`, `freshness_hours`, `is_official_confirmed`, `source_channel`, `source_channels`, `source_grade`, `audience_scope`, `audience_region_code`, `legal_completeness_score`, `legal_filled_count`, `legal_required_count`, `poll_fingerprint`, `scenarios[]`, `scenarios[].scenario_key`, `scenarios[].scenario_type`, `scenarios[].scenario_title`, `scenarios[].options[]`, `options[]`, `options[].name_validity`, `options[].scenario_key`, `options[].scenario_type`, `options[].scenario_title`, `options[].value_mid`, `options[].value_raw`, `options[].party_inferred`, `options[].party_inference_source`, `options[].party_inference_confidence`, `options[].party_inference_evidence` |
| 후보자 상세 | `GET /api/v1/candidates/{candidate_id}` | `candidates`, `candidate_profiles` | `candidate_id`, `name_ko`, `party_name`, `career_summary`, `election_history`, `profile_source`, `profile_completeness`, `profile_provenance`, `profile_source_type`, `profile_source_url`, `placeholder_name_applied` |

## 5. API-UI 필드명 일치 규칙
1. UI에서 수치표시는 항상 `value_mid` 기준
2. 원문 표시 필요 시 `value_raw` 보조 표기
3. 검증 배지는 `verified` 또는 `source_grade` 기준
4. 지역 선택의 기준 키는 `region_code` 단일 사용
5. 대시보드 요약 카드는 `audience_scope='national'`로 스코프 분리된 데이터만 사용
6. 요약 API는 `audience_scope IS NULL` 데이터를 포함하지 않는다.
7. summary/map-latest/big-matches는 `scope_breakdown`으로 스코프별 개수를 함께 노출한다.
8. 매치업 상세는 조사 스코프(`audience_scope`)와 법정 completeness(`legal_*`)를 함께 노출
9. 대시보드 계열 API의 `source_channels`는 null 대신 빈 배열(`[]`)을 기본값으로 노출
10. 매치업 상세의 법정메타 결측값은 `null`로 유지한다(숫자/날짜 모두 동일)
11. 매치업 상세의 `nesdc_enriched`는 `source_channels`에 `nesdc`가 포함되면 `true`다.
12. 매치업 상세의 `needs_manual_review`는 연결된 `review_queue`가 `pending` 또는 `in_progress`이면 `true`다.
13. 옵션별 `party_inferred=true`이면서 `party_inference_confidence < 0.8`이면 `review_queue` 검수 대상이다.
14. `source_priority`는 `source_channels` 기준으로 `official|article|mixed`를 노출한다.
15. `freshness_hours`는 공식시각(`official_release_at`) 우선으로 계산하고, 없으면 기사시각(`article_published_at`)을 사용한다.
16. `source_trace`는 `source_priority`, `source_channel`, `source_channels`, `official_release_at`, `article_published_at`, `freshness_hours`, `is_official_confirmed`를 공통 구조로 제공한다.
17. `summary`의 `source_trace`는 대표값 선택 결과(`selected_source_tier`, `selected_source_channel`)를 추가로 포함한다.
18. `map-latest`, `big-matches`, `matchups`는 `canonical_title`을 기본 제목으로 사용하고 원문 기사용 제목은 `article_title`로 분리한다.
19. 하위호환 필드(`title`, `source_priority`, `source_channel`, `source_channels`, `official_release_at`, `article_published_at`, `freshness_hours`, `is_official_confirmed`)는 deprecated 상태로 유지한다.
20. `GET /api/v1/trends/{metric}`에서 `scope=regional|local` 요청은 `region_code` 필수다.
21. trends 포인트는 동일 날짜/옵션 그룹 내 대표값 선택 trace(`source_trace.selected_source_tier`, `source_trace.selected_source_channel`)를 포함한다.
