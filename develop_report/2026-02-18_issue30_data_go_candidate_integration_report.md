# 2026-02-18 Issue #30 Data.go.kr Candidate Integration Report

## 1) 이슈
- 대상: `#30 [DEVELOP] Data.go.kr 후보자 상세(PofelcddInfo) 연동`
- 목표: `GET /api/v1/candidates/{candidate_id}`에 공공데이터 후보 상세를 병합하고, 오류 시 DB fallback 보장

## 2) 구현 내용
1. Data.go 후보 상세 서비스 추가
- 파일: `app/services/data_go_candidate.py`
- 기능:
  - `PofelcddInfoInqireService/getPoelpcddRegistSttusInfoInqire` 호출
  - timeout/retry/rate-limit/cache 정책 반영
  - XML/JSON 응답 파싱 + 후보명 매칭
  - `party_name`, `gender`, `birth_date`, `job`, `career_summary` 병합
  - 외부 호출 실패/미매칭 시 DB 값 fallback

2. API 연결
- 파일: `app/api/routes.py`
- 변경: `GET /api/v1/candidates/{candidate_id}`에서 Data.go 병합 결과 반환

3. 의존성/설정 주입
- 파일: `app/api/dependencies.py`, `app/config.py`
- 변경:
  - `get_candidate_data_go_service` dependency 추가
  - 설정 누락/환경 미구성 시 no-op 서비스로 graceful fallback

4. 환경변수 계약 반영
- 파일: `.env.example`
- 추가:
  - `DATA_GO_CANDIDATE_ENDPOINT_URL`
  - `DATA_GO_CANDIDATE_SG_ID`
  - `DATA_GO_CANDIDATE_SG_TYPECODE`
  - `DATA_GO_CANDIDATE_SD_NAME`
  - `DATA_GO_CANDIDATE_SGG_NAME`

## 3) 정책 반영 여부
1. Timeout: `timeout_sec` 설정(기본 4초)
2. Retry: `max_retries` + 지수 백오프
3. Rate-limit: `requests_per_sec` 기반 호출 간 최소 간격 보장
4. Caching: `cache_ttl_sec` 기반 in-memory 캐시
5. Fallback: key/파라미터/응답 오류 시 DB 데이터 유지

## 4) 테스트
1. 단위/계약 테스트
- `pytest`: 47 passed
- `scripts/qa/run_api_contract_suite.sh --report data/qa_api_contract_report_issue30.json`: 19/19 pass

2. 추가 테스트(신규)
- 파일: `tests/test_data_go_candidate_service.py`
- 검증:
  - 미구성 시 no-op
  - XML 응답 병합
  - retry + cache
  - 오류 fallback
  - INFO-03(데이터 없음) 비재시도

## 5) 실제 API 호출 검증 (완료기준)
- Data.go 실제 호출 기반 검증 파일: `data/data_go_candidate_live_verify.json`
- 검증 컨텍스트:
  - `sg_id=20260603`
  - `sg_typecode=2`
  - `sd_name=인천광역시`
  - `sgg_name=계양구을`
- 결과:
  - HTTP 200
  - 후보 상세 병합 성공(예: `party_name=국민의힘`, `job=세림조경건설주식회사 대표이사`)

## 6) 스키마 호환성
- `CandidateOut` 응답 스키마 변경 없음
- 기존 필드명/타입 유지
