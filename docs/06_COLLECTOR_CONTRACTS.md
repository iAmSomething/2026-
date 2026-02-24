# 수집기 최소 계약 명세

- 문서 버전: v0.5
- 최종 수정일: 2026-02-24
- 수정자: Codex

## 1. 입력 계약(JSON 스키마)
수집기 `discover/fetch/classify/extract` 단계가 다음 3개 엔티티를 전달합니다.

1. `article`
2. `poll_observation`
3. `poll_option`

코드 기준 스키마 원본:
- `src/pipeline/contracts.py`의 `ARTICLE_SCHEMA`
- `src/pipeline/contracts.py`의 `POLL_OBSERVATION_SCHEMA`
- `src/pipeline/contracts.py`의 `POLL_OPTION_SCHEMA`
- 통합 레지스트리: `INPUT_CONTRACT_SCHEMAS`

## 2. 식별자 계약
아래 식별자는 최소 필수 계약입니다.

1. `region_code`: CommonCodeService 기준 지역 코드 (예: `11-000`)
2. `office_type`: 기획 표준 enum
3. `matchup_id`: `election_id|office_type|region_code` 조합 키
4. `candidate_id`: 후보 식별자 (`cand:<normalized_name>`)

`office_type` 허용값:
1. `광역자치단체장`
2. `광역의회`
3. `교육감`
4. `기초자치단체장`
5. `기초의회`
6. `재보궐`

지역 매핑 원칙:
1. 시도 레벨 우선코드: `xx-000`
2. 시군구 레벨: `xx-yyy` 형식(예: `11-680` 강남구)
3. 매핑 불가 시 임시코드를 출력하지 않고 `mapping_error`로 `review_queue` 전송

## 3. 정규화 계약
`poll_option` 값 정규화는 아래 필드를 반드시 채웁니다.

1. `value_raw`
2. `value_min`
3. `value_max`
4. `value_mid`
5. `is_missing`
6. `margin_of_error`

정규화 규칙:
1. 단일값 `38%` -> `min=max=mid=38`
2. 범위 `53~55%` -> `min=53`, `max=55`, `mid=54`
3. 밴드 `60%대` -> `min=60`, `max=69`, `mid=64.5`
4. 결측 `언급 없음` -> `is_missing=true`, 수치 필드 null

구현 위치:
- `src/pipeline/contracts.py`의 `normalize_value`

## 4. 오류 계약(review_queue 전송 포맷)
실패 건은 `review_queue`로 아래 포맷으로 전송합니다.

필수 필드:
1. `id`
2. `entity_type`
3. `entity_id`
4. `issue_type`
5. `status` (`pending|approved|rejected`)
6. `stage` (`discover|fetch|classify|extract|normalize|load`)
7. `error_code`
8. `error_message`
9. `created_at`

보조 필드:
1. `source_url`
2. `payload` (원인 분석용 구조화 컨텍스트)

`issue_type` 고정 taxonomy:
1. `discover_error`
2. `fetch_error`
3. `classify_error`
4. `extract_error`
5. `mapping_error`
6. `ingestion_error`

코드 기준 스키마 원본:
- `src/pipeline/contracts.py`의 `REVIEW_QUEUE_SCHEMA`
- 생성 헬퍼: `new_review_queue_item(...)`

## 5. 실행 예시
```bash
python -m src.pipeline.run_collector \
  --seed "https://example.com/news/1" \
  --print-contracts
```

## 6. 실데이터 오류분석 운영
1. 50건 오류분석:
```bash
PYTHONPATH=. .venv/bin/python scripts/analyze_collector_real_errors.py
```
2. 실기사 라벨셋(30건) 생성:
```bash
PYTHONPATH=. .venv/bin/python scripts/build_real_article_labelset.py
```
3. 실기사 precision 측정:
```bash
PYTHONPATH=. .venv/bin/python scripts/evaluate_collector_real_precision.py
```

4. CommonCodeService 코드 동기화:
```bash
PYTHONPATH=. .venv/bin/python scripts/sync_common_codes.py \
  --region-url "$COMMON_CODE_REGION_URL" \
  --party-url "$COMMON_CODE_PARTY_URL" \
  --election-url "$COMMON_CODE_ELECTION_URL"
```

5. discovery v1 실행(후속 classify 입력 생성):
```bash
PYTHONPATH=. .venv/bin/python scripts/run_discovery_v1.py \
  --target-count 100 \
  --per-query-limit 10 \
  --output-dir data
```

6. discovery v1.1 실행(ROBOTS_DISALLOW 완화):
```bash
PYTHONPATH=. .venv/bin/python scripts/run_discovery_v11.py \
  --target-count 100 \
  --per-query-limit 10 \
  --per-feed-limit 40 \
  --output-dir data \
  --baseline-report data/discovery_report_v1.json
```

## 7. Discovery v1.1 소스 전략
1. 소스 우선순위:
- 1순위: 언론사 직접 RSS (`publisher_rss`)
- 2순위: Google RSS query (`google_rss`)
2. canonicalization:
- `news.google.com/rss/articles/...`는 tracking query를 제거한 안정 경로로 정규화
3. robots 완화:
- `news.google.com` 도메인은 blocklist로 처리
- 본문 fetch 대신 RSS title/summary 기반 fallback article 생성
4. 비교 지표:
- `fetch_fail_rate` (v1 대비)
- `valid_article_rate` (v1 대비)

## 8. Classify 선별게이트 규칙
`POLL_REPORT` 기사에 대해 extract 이전에 선별게이트를 적용한다.

통과 조건:
1. 후보명+수치 신호 존재 (`extract_candidate_pairs(...)` 결과 1개 이상)
2. 지역/직위 매핑 가능 (`_extract_region_office(...)` 성공)
3. 정책/정성 단독 기사 아님

제외 규칙:
1. `국정지지율/정당지지도/국정평가` 중심 기사 + 선거 직위 힌트 부재 -> 제외
2. `찬성/반대/호감도` 중심 기사 + 후보 수치 페어 부재 -> 제외

게이트 실패 처리:
1. `issue_type=classify_error`
2. `error_code`:
- `GATE_POLICY_QUALITATIVE_ONLY`
- `GATE_NO_CANDIDATE_NUMERIC_SIGNAL`
- `GATE_REGION_OFFICE_UNMAPPED`

비교 실험 실행:
```bash
PYTHONPATH=. .venv/bin/python scripts/evaluate_classify_gate_effect.py
```

## 9. Extractor v2 (본문 기반) 규칙
1. 기본 추출 모드:
- `extract_candidate_pairs(..., mode="v2")`
2. v2 처리 순서:
- 본문 클리닝(`_clean_body_for_extraction`)으로 광고/메타/URL 노이즈 제거
- 후보/수치 신호 문장 추출(`_candidate_value_signals`)
- `MATCHUP_RE` 우선, 실패 시 `NAME_VALUE_RE` fallback
3. 후보명 필터:
- 비후보 토큰/정책 토큰(예: `찬성`, `반대`, `정부`, `정당`) 제외
4. taxonomy 유지:
- `issue_type`는 기존 enum 유지(`extract_error`)
- 원인 세분화는 `error_code`로 처리

v2 `extract_error` 세분화 코드:
1. `POLICY_ONLY_SIGNAL`
2. `NO_NUMERIC_SIGNAL`
3. `NO_TITLE_CANDIDATE_SIGNAL`
4. `NO_BODY_CANDIDATE_SIGNAL`

성능 비교 실행:
```bash
PYTHONPATH=. .venv/bin/python scripts/evaluate_extractor_v2_compare.py
```

## 10. 도메인 품질 운영
1. 도메인별 fetch/parse/extract 성공률 집계:
```bash
PYTHONPATH=. .venv/bin/python scripts/analyze_domain_extraction_quality.py
```
2. 산출물:
- `data/collector_domain_extraction_quality_report.json`
3. 주간 템플릿:
- `Collector_reports/collector_weekly_domain_quality_template.md`

## 11. 수집기 리포트 health/risk 분리 계약
리포트 JSON에서 `acceptance_checks`와 `risk_signals`(또는 `anomaly_signals`)는 의미를 분리한다.

1. `acceptance_checks`
- 의미: 성공/정상 조건 검증 결과
- 규칙: `true`가 바람직한 상태
- 예시:
  - `ingest_records_ge_30`
  - `safe_window_policy_applied`
  - `threshold_miss_review_queue_synced`

2. `risk_signals` (또는 `anomaly_signals`)
- 의미: 문제/경고 이벤트 존재 여부
- 규칙: `true`는 경고 신호(즉, 위험 존재)
- 예시:
  - `threshold_miss_present`
  - `adapter_failure_present`
  - `before_delay_over_96h_present`

3. 역의미 금지 규칙
- `acceptance_checks`에 "문제 발생 여부" 플래그를 두지 않는다.
- 문제 발생 여부는 `risk_signals`/`anomaly_signals`로만 표현한다.

4. 하위호환 권고
- 구버전 소비자가 있을 경우 필드 삭제 대신 아래 순서로 전환한다.
  1) 역의미 필드를 `risk_signals`로 이관
  2) `acceptance_checks`에는 동기화/정합성 조건만 유지
  3) 문서/테스트를 같은 PR에서 함께 갱신
