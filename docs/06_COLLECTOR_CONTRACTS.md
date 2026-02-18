# 수집기 최소 계약 명세

- 문서 버전: v0.2
- 최종 수정일: 2026-02-18
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
