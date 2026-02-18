# 배포 환경 최종안 (2026-02-18 기준)

## 요약
1. 최종 선택: `Supabase(Postgres) + FastAPI(Railway) + Next.js(Vercel)`.
2. 이유(추론): 비개발자 기준으로 운영 난이도는 낮추고, Python 기반 기사 추출/정규화 파이프라인은 그대로 유지 가능.
3. 핵심 원칙: DB는 Supabase 단일화, API/배치는 FastAPI로 분리, 프론트는 Vercel로 배포 자동화.

## 아키텍처 결정 (Decision Complete)
1. DB/인증/스토리지: Supabase.
2. 백엔드 API: Railway에 FastAPI 1개 서비스(`api`).
3. 배치 파이프라인: Railway Cron Job 1개(`ingest`), 2시간 주기.
4. 프론트엔드: Vercel(Next.js) 1개 프로젝트.
5. 도메인:
`app.<domain>` -> Vercel
`api.<domain>` -> Railway
Supabase는 private connection + service key로만 접근.
6. 리전:
Supabase와 Railway를 같은 권역(APAC)으로 정렬.
Vercel 함수 region도 DB 근접 region으로 지정.
7. 운영 정책:
초기에는 단일 리전/단일 복제본.
트래픽 증가 시 API만 수평 확장.

## 왜 이 조합이 최적인가
1. Supabase는 프로젝트당 관리형 Postgres + 자동 API/백업 운영 모델이라 DB 운영 부담이 낮다.
2. FastAPI는 Python 생태계(NLP/정규식/LLM 후처리)와 궁합이 좋고 Railway에 배포 가이드가 명확하다.
3. Vercel은 Next.js 배포 자동화와 CDN이 강해 대시보드 UX 성능 확보가 쉽다.
4. 스케줄은 GitHub Actions도 가능하지만, 스케줄 지연/드롭 가능성이 있어(공식 문서 명시) 운영 안정성 우선이면 Railway Cron이 더 적합.

## 공개 API/인터페이스 확정
1. `GET /api/v1/dashboard/summary`
2. `GET /api/v1/dashboard/map-latest`
3. `GET /api/v1/dashboard/big-matches?limit=3`
4. `GET /api/v1/regions/search?q=...`
5. `GET /api/v1/regions/{region_code}/elections`
6. `GET /api/v1/matchups/{matchup_id}`
7. `GET /api/v1/candidates/{candidate_id}`
8. `POST /api/v1/jobs/run-ingest` (내부 토큰 필요, cron 전용)

## 배포/운영 설계
1. Git 전략:
`main` push -> Vercel 프론트 자동 배포 + Railway API 자동 배포.
2. 비밀키:
Supabase `anon key`, `service role key`, DB URL을 플랫폼 Secret으로만 저장.
3. 마이그레이션:
Supabase SQL migration 파일 기반으로 관리, 배포 전후 자동 적용.
4. 비용가드:
Supabase `Spend Cap ON` 기본.
Railway/Vercel 사용량 알림 활성화.
5. 장애복구:
`ingestion_runs` 테이블로 idempotent 실행.
같은 시각 중복 실행 방지 lock 적용.

## 테스트/검증 시나리오
1. 배포 검증:
프론트/백엔드 URL 헬스체크, CORS, TLS 확인.
2. 데이터 경로:
기사 수집 -> 추출 -> 정규화 -> 검수 큐 -> 공개 API 노출까지 E2E.
3. 스케줄:
2시간 주기 실행 성공률, 실패 재시도, 중복실행 방지 확인.
4. 성능:
메인 대시보드 P95 응답시간, 지도 hover API 응답시간 측정.
5. 비용:
월 예상 호출량 기준으로 quota 초과 항목 경고 테스트.

## 단계별 롤아웃
1. Phase 1 (MVP):
단일 Supabase 프로젝트 + Railway API/cron + Vercel 프론트.
2. Phase 2:
검수 UI 강화, API 캐시, 알림/모니터링 도입.
3. Phase 3:
리전 다중화 또는 read replica 검토.

## 가정/기본값
1. 초기 사용자 수는 중소규모(수천~수만 MAU)로 가정.
2. 기사 추출 배치 1회 실행이 10분 내외가 되도록 청크 처리(초과 시 배치 분할).
3. 예측 모델은 제외하고 “관측 데이터 시각화”에 집중.
4. 운영 인력 1인 기준으로 수동개입 최소화가 최우선.

## 근거 문서 (공식)
1. Supabase billing/usage: [About billing](https://supabase.com/docs/guides/platform/billing-on-supabase)
2. Supabase cost control: [Spend Cap](https://supabase.com/docs/guides/platform/cost-control#spend-cap)
3. Supabase cron: [Cron overview](https://supabase.com/docs/guides/cron)
4. Railway FastAPI 배포: [Deploy a FastAPI App](https://docs.railway.com/guides/fastapi)
5. Railway 요금: [Railway Pricing](https://docs.railway.com/pricing)
6. Vercel Next.js 배포: [Next.js on Vercel](https://vercel.com/docs/frameworks/full-stack/nextjs)
7. Vercel 요금: [Vercel Pricing](https://vercel.com/pricing)
8. GitHub schedule 제약(UTC/지연 가능성): [Events that trigger workflows](https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows)
