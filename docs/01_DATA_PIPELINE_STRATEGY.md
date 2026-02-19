# 데이터 파이프라인 전략

- 문서 버전: v0.2
- 최종 수정일: 2026-02-19
- 수정자: Codex

## 1. End-to-End 흐름
1. 기사 후보 수집(`discover`)
2. 여론조사 포함 여부 판별(`classify`)
3. 기사 본문 추출/정제(`parse`)
4. 수치/문항/매치업 추출(`extract`)
5. 정규화 및 코드 매핑(`normalize`)
6. 공식 출처 대조(`verify`)
7. 검수 큐 처리(`review`)
8. 공개 데이터 반영(`publish`)

## 2. 기사 수집 전략
### 2.1 수집 대상
1. 뉴스 검색 API/RSS 기반 `여론조사` 관련 기사
2. 선거명/지역명/직책명을 결합한 키워드 쿼리

### 2.1-A 준법/요청 정책
1. robots.txt 허용 경로만 수집(RFC 9309 기준)
2. 사이트별 요청 빈도 제한(rate limit) 적용
3. 금지/차단 응답은 즉시 스킵하고 사유 로깅

### 2.2 수집 메타 필드
- `url`, `title`, `publisher`, `published_at`, `snippet`, `collected_at`, `raw_hash`

### 2.3 중복 제거
- 1차: URL canonicalization
- 2차: `title + published_at + publisher` 해시 비교

## 3. 여론조사 기사 판별 전략
### 3.1 규칙 기반 1차 필터
- 포함 키워드: `여론조사`, `표본`, `오차범위`, `응답률`, `조사기관`
- 제외 키워드: 단순 칼럼/사설 패턴

### 3.2 분류 모델 2차 판별
- 라벨: `POLL_REPORT`, `POLL_MENTION`, `NON_POLL`
- 저장: `classification_label`, `classification_confidence`

### 3.3 운영 룰
1. `POLL_REPORT` -> 자동 추출
2. `POLL_MENTION` -> 보류 후 검수 우선
3. `NON_POLL` -> 아카이브

## 4. 추출 전략(규칙+LLM)
### 4.1 규칙 기반 추출
- 퍼센트: `38%`
- 범위: `53~55%`
- 밴드: `60%대`
- 대결문: `A 40% vs B 36%`

### 4.2 LLM 보완 추출
- 문항명, 지역명, 직책, 후보명의 문맥 매핑
- 규칙 실패 영역만 선택 호출(비용 통제)

### 4.3 근거 저장
- `evidence_text`, `evidence_start`, `evidence_end`, `source_url`
- 기본값: 원문 전체가 아닌 최소 스팬 저장(저작권 리스크 완화)

## 5. 검증 게이트
1. 공식 데이터 또는 높은 신뢰 출처와 조사 단위 비교
2. 일치: `verified=true`
3. 불일치/불명확: `review_queue` 등록 후 공개 보류

## 6. 실패 처리
1. 네트워크 실패: 재시도(지수 백오프)
2. 파싱 실패: 원문 스냅샷 보존 후 재처리 큐
3. 코드 매핑 실패: `mapping_error` 상태로 검수 큐 이동
4. 중복 적재 시도: idempotency key로 upsert
5. robots/약관 위반 가능 URL: 영구 제외 목록 등록

## 6.1 상대시점 변환 정책
1. 기본 정책 `strict_fail`:
- 상대시점 문구(예: 어제/지난주) + `article.published_at` 결측이면 변환 실패(`date_inference_mode=strict_fail_blocked`)로 기록하고 검수 큐 라우팅
2. 선택 정책 `allow_estimated_timestamp`:
- `article.collected_at`를 fallback 기준시각으로 사용해 추정 변환(`date_inference_mode=estimated_timestamp`)
3. 저신뢰 추론(`date_inference_confidence < 0.8`)은 정책과 무관하게 검수 큐 라우팅

## 7. 배치 주기
- 기본: 2시간 간격
- 수동 실행: 내부 API `POST /api/v1/jobs/run-ingest`
