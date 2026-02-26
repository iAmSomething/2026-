# 2026-02-26 Issue #328 전국 요약지표 최신성 보정 v2 보고서

## 1) 이슈
- Issue: #328 `[COLLECTOR][P0] 전국 요약지표 최신성 보정 v2(NBS/공표기준 우선)`
- URL: https://github.com/iAmSomething/2026-/issues/328

## 2) 실행 요약
- 실행 모드:
  - 운영 DB direct 접속은 로컬 `DATABASE_URL` 인증 실패로 차단.
  - 우회로로 운영 API + Supabase PostgREST 증빙 경로 사용.
- 재적재 실행:
  - `run_id=523`
  - `processed_count=15` (최근 14일 윈도우 + 최신일(article/official) 충돌 probe 1건)
  - `error_count=0`
  - `status=success`
- 생성 산출물:
  - `data/issue328_national14_reingest_payload.json`
  - `data/issue328_national14_reingest_log.json`
  - `data/issue328_summary_pre_snapshot.json`
  - `data/issue328_summary_post_snapshot.json`
  - `data/issue328_summary_before_after_diff.json`
  - `data/issue328_expected_vs_actual_diff.json`
  - `data/issue328_latest_selection_evidence_before.json`
  - `data/issue328_latest_selection_evidence_after.json`

## 3) 코드 변경
1. summary latest 선택 로직 보강(코드)
- `app/services/repository.py`
- 변경 내용:
  - 기존: `MAX(survey_end_date)`만으로 latest observation 선택
  - 변경: 아래 순서로 `ROW_NUMBER()` tie-break
    1. `survey_end_date DESC`
    2. `COALESCE(official_release_at, article_published_at, observation_updated_at) DESC`
    3. `source_rank(nesdc=2, article=1, none=0) DESC`
    4. `observation_id DESC`
- 목적:
  - 같은 조사종료일 다건일 때 official/공표기준 우선 선택 보장

2. 스크립트 추가
- `scripts/run_issue328_national_summary_freshness_v2.py`
  - DB direct 모드(로컬/운영 DB 직접 연결 시)
- `scripts/run_issue328_national_summary_freshness_v2_remote.py`
  - 운영 API + Supabase 증빙 모드(이번 실행에 사용)

3. 테스트
- `tests/test_repository_dashboard_summary_scope.py`
  - 최신 선택 쿼리 tie-break 계약 검증으로 갱신
- `tests/test_issue328_national_summary_freshness_v2_script.py`
  - 14일 윈도우 payload + 최신일 source conflict probe + 목표값 생성 검증

## 4) 검증 결과
- 실행:
  - `PYTHONPATH=. /Users/gimtaehun/election2026_codex/.venv/bin/pytest -q tests/test_repository_dashboard_summary_scope.py tests/test_issue328_national_summary_freshness_v2_script.py`
  - `4 passed`
- 문법검증:
  - `PYTHONPATH=. /Users/gimtaehun/election2026_codex/.venv/bin/python -m py_compile scripts/run_issue328_national_summary_freshness_v2.py scripts/run_issue328_national_summary_freshness_v2_remote.py`
  - 성공

## 5) PM 필수 산출물
1. 최근 14일 전국 스코프 재적재 로그
- `data/issue328_national14_reingest_log.json`
- 핵심:
  - `run_id=523`
  - `records_in_payload=15`
  - `processed_count=15`
  - `error_count=0`

2. 카드별 latest 선택 근거 쿼리 결과
- before: `data/issue328_latest_selection_evidence_before.json`
  - `party_support` 최신 선택이 article(`demo-30d-party-1`, 2026-02-23)
- after: `data/issue328_latest_selection_evidence_after.json`
  - `party_support/president_job_approval/election_frame` 모두
  - `rn=1`이 `obs-issue328-national-2026-02-26-official-15`(source=`nesdc`, rank=2)
  - `rn=2`는 동일 날짜 article probe(source=`article`, rank=1)

3. 기대값 대비 차이표
- 파일: `data/issue328_expected_vs_actual_diff.json`
- post 기준:

| 카드 | 항목 | 기대 | 실제 | 차이 |
|---|---|---:|---:|---:|
| party_support | 더불어민주당 | 45.0 | 43.0 | -2.0 |
| party_support | 국민의힘 | 17.0 | 17.0 | 0.0 |
| president_job_approval | 대통령 직무 긍정평가 | 67.0 | 67.0 | 0.0 |
| president_job_approval | 대통령 직무 부정평가 | 25.0 | 29.0 | +4.0 |
| election_frame | 국정안정론 | 53.0 | 47.0 | -6.0 |
| election_frame | 국정견제론 | 34.0 | 45.0 | +11.0 |

## 6) summary API before/after diff
- 파일: `data/issue328_summary_before_after_diff.json`
- before(보정 전):
  - `party_support=2`, `president_job_approval=0`, `election_frame=2`
  - `party_support` 최신값은 article(민주 35/국힘 38)
- after(재적재 후):
  - `party_support=4`, `president_job_approval=4`, `election_frame=6`
  - 카드 non-empty는 충족
  - 동일 카드 내 article/official 중복 행이 함께 노출됨(운영 API tie-break 미반영 상태)

## 7) 완료기준 대조
1. 최신값 반영 시점/출처 명시
- 충족 (보고서 + evidence JSON에 survey_end_date/source_channel/source_priority_rank 명시)

2. `party_support` / `president_job_approval` / `election_frame` non-empty
- 충족 (`post_snapshot` 기준 모두 non-empty)

3. summary API stale/age 근거 일관성
- 부분 충족
- 근거:
  - 데이터 레벨 latest 근거(`evidence_after`)는 official 우선으로 정합
  - 운영 API 응답(`post_snapshot`)은 동일 option 중복 행을 함께 반환하여 체감 최신값 해석이 흔들림

4. source priority(official/nesdc/article) 규칙 보고서 명시
- 충족 (본 보고서 3/5장 + `issue328_national14_reingest_log.json` 내 `source_priority_policy`)

## 8) 의사결정 필요사항
1. #328 코드패치(`app/services/repository.py`) 운영 배포 승인 필요
- 배포 전: 운영 API가 동일 날짜 article/official 중복을 함께 반환
- 배포 후 기대: 각 카드 option_type별 official/공표 우선 단일 latest observation 선택

2. API 출력 중복 허용 정책 확정 필요
- 현재 실제 UX에서는 동일 option_name 중복 노출 가능
- 정책안:
  - A안: API에서 단일 latest만 반환(권장)
  - B안: 다건 반환 유지 + UI에서 source_priority 기반 필터

3. #328 synthetic observation 유지 여부
- 현재 `obs-issue328-national-*` key로 최신성 보정 데이터가 운영에 반영됨
- 유지/정리 정책 확정 필요
