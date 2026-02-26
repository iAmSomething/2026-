# 데이터 모델 및 정규화 명세

- 문서 버전: v0.2
- 최종 수정일: 2026-02-19
- 수정자: Codex

## 1. 핵심 테이블

## 1.1 `articles`
- 목적: 수집된 기사 원천 저장
- 주요 컬럼: `id`, `url`, `title`, `publisher`, `published_at`, `raw_text`, `raw_hash`, `created_at`

## 1.2 `article_poll_mentions`
- 목적: 기사 내 조사 단위(문항/매치업) 추출 결과 저장
- 주요 컬럼: `id`, `article_id`, `label`, `confidence`, `evidence_text`, `evidence_start`, `evidence_end`, `extractor_type`, `extractor_version`

## 1.3 `poll_observations`
- 목적: 조사 메타 정보 저장
- 주요 컬럼:
- `id`, `survey_name`, `pollster`, `survey_start_date`, `survey_end_date`
- `confidence_level`, `sample_size`, `response_rate`, `margin_of_error`
- `sponsor`, `method`
- `region_code`, `office_type`, `matchup_id`, `verified`, `source_grade`, `ingestion_run_id`
- `audience_scope`(`national|regional|local`), `audience_region_code`, `sampling_population_text`
- `legal_completeness_score`, `legal_filled_count`, `legal_required_count`, `date_resolution`
- `date_inference_mode`, `date_inference_confidence`
- `poll_fingerprint`, `source_channel`(`article|nesdc`), `source_channels`(다중 provenance)

## 1.4 `poll_options`
- 목적: 조사 선택지(후보/문항값) 저장
- 주요 컬럼: `id`, `observation_id`, `option_type`, `option_name`, `value_raw`, `value_min`, `value_max`, `value_mid`, `is_missing`, `party_inferred`, `party_inference_source`, `party_inference_confidence`

## 1.5 `regions`
- 목적: 시도/시군구 코드 사전
- 주요 컬럼: `region_code`, `sido_name`, `sigungu_name`, `admin_level`, `parent_region_code`

## 1.6 `matchups`
- 목적: 지역+직책+선거 기준 매치업 정의
- 주요 컬럼: `matchup_id`, `election_id`, `office_type`, `region_code`, `title`, `is_active`

## 1.7 `candidates`
- 목적: 후보자 마스터
- 주요 컬럼: `candidate_id`, `name_ko`, `party_name`, `gender`, `birth_date`, `job`, `profile_updated_at`

## 1.8 `candidate_profiles`
- 목적: 후보자 상세 약력/출마 정보
- 주요 컬럼: `id`, `candidate_id`, `career_summary`, `election_history`, `source_type`, `source_url`

## 1.9 `review_queue`
- 목적: 수동 검수 대상 관리
- 주요 컬럼: `id`, `entity_type`, `entity_id`, `issue_type`, `status`, `assigned_to`, `review_note`, `created_at`

## 1.10 `ingestion_runs`
- 목적: 배치 실행 이력
- 주요 컬럼: `id`, `run_type`, `started_at`, `ended_at`, `status`, `processed_count`, `error_count`, `extractor_version`, `llm_model`

## 2. 정규화 규칙
1. 단일값(`38%`): `value_min=value_max=value_mid=38`
2. 범위(`53~55%`): `value_min=53`, `value_max=55`, `value_mid=54`
3. 밴드(`60%대`): `value_min=60`, `value_max=69`, `value_mid=64.5`
4. 결측(`언급 없음`): `is_missing=true`, 수치 컬럼 null
5. 단위: `%`를 `0~100` float로 저장
6. 원문 보존: `value_raw`에 기사 원문 표현 저장
7. 오차범위(`±x%`)가 명시되면 `margin_of_error` 저장, 없으면 null
8. 스코프 정규화: `audience_scope`는 `national|regional|local`만 허용
9. 법정필수 completeness: `legal_completeness_score = legal_filled_count / legal_required_count` 기준(입력값 보존)

## 3. 식별자/코드 매핑 규칙
1. `election_id`: 선거 회차 ID
2. `office_type`: 광역단체장/광역의회/교육감/기초단체장/기초의회/재보궐
3. `region_code`: 시도/시군구 표준 코드
4. `matchup_id`: `election_id + office_type + region_code` 조합 키

## 4. Data.go.kr API 연동 반영
### 필수 연동
1. `CommonCodeService`: 지역/정당/선거 코드 정규화
2. `PofelcddInfoInqireService`: 후보자 상세 데이터 보강

### 선택 연동
1. `WinnerInfoInqireService2`: 당선인 정보(선거 후)
2. `VoteXmntckInfoInqireService2`: 투표/개표 참고 지표
3. `PartyPlcInfoInqireService`: 정당 정책 정보

## 5. 공용 API 단일 소스 명세
### 공개 API
1. `GET /api/v1/dashboard/summary`
2. `GET /api/v1/dashboard/map-latest`
3. `GET /api/v1/dashboard/big-matches`
4. `GET /api/v1/dashboard/quality`
5. `GET /api/v1/regions/search`
6. `GET /api/v1/regions/{region_code}/elections`
7. `GET /api/v1/matchups/{matchup_id}`
8. `GET /api/v1/candidates/{candidate_id}`

### 내부 운영 API
1. `POST /api/v1/jobs/run-ingest`
2. `POST /api/v1/review/{item_id}/approve`
3. `POST /api/v1/review/{item_id}/reject`

## 6. 스코프 분리 집계 규칙
1. `GET /api/v1/dashboard/summary`는 `audience_scope='national'` 데이터만 집계한다.
2. `audience_scope IS NULL` 관측치는 summary 집계에서 제외한다.
3. `audience_scope='regional'|'local'` 관측치는 summary 집계에서 제외한다.
4. `GET /api/v1/dashboard/summary`, `GET /api/v1/dashboard/map-latest`, `GET /api/v1/dashboard/big-matches`는 `scope_breakdown`을 함께 노출한다.
5. `GET /api/v1/dashboard/summary`는 응답 루트에 `data_source`(`official|article|mixed`)를 노출한다.
6. `GET /api/v1/matchups/{matchup_id}`는 관측치가 없어도 `matchups` 메타가 존재하면 `200`을 반환하며 `has_data=false`, `options=[]`를 반환한다.
7. `GET /api/v1/regions/search`는 `has_data`, `matchup_count` 보조 필드를 포함한다.

## 6.1 운영 품질 요약 규칙 (`GET /api/v1/dashboard/quality`)
1. `freshness_p50_hours`, `freshness_p90_hours`는 검증 완료(`verified=true`) 관측치의 freshness 분포 백분위를 시간 단위로 노출한다.
2. freshness 기준 시각은 `official_release_at` 우선, 없으면 `article_published_at`, 둘 다 없으면 관측치 `updated_at`을 사용한다.
3. `official_confirmed_ratio`는 `source_channels`에 `nesdc`가 포함된 관측치 비율이다.
4. `needs_manual_review_count`는 `review_queue`의 `pending|in_progress` 건수 합이다.
5. `source_channel_mix`는 관측치 기준 `article_ratio`, `nesdc_ratio`를 각각 0~1 범위로 노출한다.
6. 데이터가 없으면 percentile 필드는 `null`, ratio/count 필드는 `0`으로 응답한다.
7. v2 확장 필드:
- `quality_status`: `healthy|warn|critical`
- `freshness.status`: freshness 분포 임계치 기반 상태
- `freshness.over_24h_ratio`, `freshness.over_48h_ratio`: freshness 지연 비율
- `official_confirmation.status`: 공식확정 비율 임계치 기반 상태
- `official_confirmation.unconfirmed_count`: 미공식 확정 건수
- `review_queue.pending_count`, `review_queue.in_progress_count`, `review_queue.pending_over_24h_count`

## 7. 중복제어(fingerprint) 규칙
1. fingerprint 기본 입력: `pollster`, `sponsor`, `survey_start_date`, `survey_end_date`, `region_code(or region_text)`, `sample_size`, `method`
2. 입력 정규화 후 `sha256`으로 `poll_fingerprint` 생성해 저장한다.
3. 동일 fingerprint 다중 소스 병합 시 메타 필드는 `nesdc` 우선, 문맥(기사 제목 기반 `survey_name`)은 `article` 보강 우선으로 적용한다.
4. 동일 fingerprint에서 핵심 식별 필드 충돌 시 `review_queue.issue_type='DUPLICATE_CONFLICT'`로 분기한다.
5. 핵심 식별 필드 비교는 형식 차이를 정규화해 판정한다(`sample_size` 숫자형, 날짜 포맷 통일, `region_code` 공백/대소문자 보정).
6. `source_grade`는 병합 시 품질 우선(`A>B>C>D`)으로 선택해 후행 저품질 소스로 다운그레이드되지 않게 유지한다.

## 8. provenance 다중 출처 규칙
1. 하위호환을 위해 `source_channel` 단일값은 유지한다.
2. 신규 `source_channels`는 채널 집합(`article`, `nesdc`)을 누적 저장한다.
3. 병합 후 `source_channel`은 기존 규칙(`nesdc` 존재 시 `nesdc`)으로 유지하고, 상세 provenance는 `source_channels`로 조회한다.
4. 기존 레거시 데이터는 마이그레이션 시 `source_channels = [source_channel]`로 백필한다.
5. API 파생 필드:
- `source_priority`: `official|article|mixed`
- `is_official_confirmed`: `source_channels`에 `nesdc` 포함 시 `true`
- `official_release_at`: 공식소스 포함 시 관측치 최신 갱신시각 기준
- `article_published_at`: 연결 기사의 `published_at`
- `freshness_hours`: `official_release_at` 우선, 없으면 `article_published_at` 기준 현재시각과의 시간차

## 9. 법정메타 null/결측 정책
1. 수집기에서 값이 없거나 추론 불가인 경우 `survey_start_date`, `survey_end_date`, `confidence_level`, `margin_of_error`, `response_rate`, `sample_size`는 `null` 저장한다.
2. `audience_scope`, `audience_region_code`도 불명확하면 `null` 저장한다.
3. API는 DB 값을 그대로 노출하며, 결측은 `null`로 유지한다.
4. 상대시점 추론 결과는 `date_inference_mode`, `date_inference_confidence`에 저장한다.

## 10. 정당 추정 메타 정책
1. 옵션 단위 정당 추론 결과는 `party_inferred`, `party_inference_source`, `party_inference_confidence`로 저장한다.
2. `party_inferred=false`면 `party_inference_source`, `party_inference_confidence`는 `null` 허용이다.
3. `party_inference_confidence < 0.8`이면 `review_queue.issue_type='party_inference_low_confidence'`로 검수 큐에 적재한다.
