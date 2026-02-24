# [COLLECTOR][S5] live-news green 이후 실데이터 품질 Post-check 보고서 (#248)

## 1) 분석 대상
- 기준 run: `22338262595` (collector-live-news-schedule first green)
- 아티팩트 경로:
  - `data/verification/issue248_run_22338262595_artifacts/collector-live-news-artifacts/collector_live_news_v1_report.json`
  - `data/verification/issue248_run_22338262595_artifacts/collector-live-news-artifacts/collector_live_news_v1_review_queue_candidates.json`
  - `data/verification/issue248_run_22338262595_artifacts/collector-live-news-artifacts/collector_live_news_v1_ingest_runner_report.json`
- 분석 요약 JSON:
  - `data/verification/issue248_live_news_postcheck_summary.json`

## 2) 지표표
| Metric | Value |
|---|---:|
| ingest_count | 37 |
| threshold_miss_rate | 1.0000 |
| fallback_fetch_count | 63 |
| review_queue_mix.fetch_error | 63 (59.43%) |
| review_queue_mix.extract_error | 42 (39.62%) |
| review_queue_mix.mapping_error | 1 (0.94%) |

## 3) completeness / threshold miss 분포
- threshold: `0.8`
- avg/min/max: `0.1802 / 0.1667 / 0.3333`
- score value 분포:
  - `0.1667`: 34건
  - `0.3333`: 3건
- score bucket 분포:
  - `<0.2`: 34건
  - `0.2~<0.4`: 3건
- threshold miss: `37/37 (100%)`
- missing field 집중:
  - `sponsor/sample_size/response_rate/margin_of_error`: 각 37건 누락
  - `survey_period`: 34건 누락

## 4) ingest runner 신호
- 최종 상태: `success=true`, `http_status=200`, `job_status=success`
- 시도: 3회
  - 1~2회 timeout
  - 3회 성공

## 5) 해석
- 런 자체는 green이며 ingest 수량 기준(`>=30`)은 충족했지만, 추출 품질은 threshold 기준에서 전량 미달입니다.
- review_queue의 과반이 `fetch_error(ROBOTS_BLOCKLIST_BYPASS)`로, fetch 단계 병목이 가장 큽니다.
- completeness 저하는 법정필수 필드 파싱 부재가 직접 원인입니다.

## 6) 다음 튜닝 우선순위(2개)
1. 법정필수 필드 추출 강화(최우선)
- 대상: `sponsor/sample_size/response_rate/margin_of_error/survey_period`
- 방법: 본문/표 캡션 패턴팩 + 수치 정규화 파서 확장 + 필드별 fallback 규칙
- 기대효과: `threshold_miss_rate` 직접 하락

2. fetch 차단 대응 경로 개선
- 대상: `ROBOTS_BLOCKLIST_BYPASS` 대량 발생 소스
- 방법: 도메인별 fetch 정책 분기(허용 소스 직수집 + 차단 소스 대체 경로/메타수집) 및 discovery 품질 게이트 재조정
- 기대효과: `fallback_fetch_count`/`fetch_error` 비중 축소, 추출 가능 문서 비율 상승

## 7) 완료 기준 충족 여부
- `Collector_reports/` post-green 분석 보고서 제출: 충족
- 지표표(ingest_count, threshold_miss_rate, fallback_fetch_count, review_queue_mix) 포함: 충족
