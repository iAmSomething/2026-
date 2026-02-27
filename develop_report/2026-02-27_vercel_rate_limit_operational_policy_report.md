# 2026-02-27 Vercel Rate-Limit Operational Policy Report

## 1) Scope
- Issue: #491
- Goal: Separate Vercel rate-limit noise from functional quality signals so PR flow is not blocked by transient deploy throttling.

## 2) Decision
- `Deployment rate limited` (or equivalent rate-limit error) is treated as **non-blocking deploy signal**.
- Functional gate remains **staging smoke evidence** (`staging-smoke`) rather than preview deploy success alone.

## 3) Changes
1. Workflow policy (`.github/workflows/vercel-preview.yml`)
- Deploy step now distinguishes:
  - hard failure (non-rate-limit): fail workflow
  - rate-limit failure: warn + continue (non-blocking)
- Verify step handles `rate_limited` mode without failing run.
- Issue comment split:
  - normal preview URL comment (success path)
  - explicit `rate_limited_non_blocking` policy comment (rate-limit path)

2. PR template separation (`.github/pull_request_template.md`)
- Added `Deploy Verification` section with two evidence paths:
  - Vercel preview URL proof
  - or staging smoke proof when rate-limited

3. Deployment docs update (`docs/04_DEPLOYMENT_AND_ENVIRONMENT.md`)
- Added explicit non-blocking rate-limit policy and fallback evidence rule.

## 4) Expected Effect
- Reduce unnecessary PR waiting caused by Vercel throttling noise.
- Keep feature validation quality signal anchored on staging smoke / API checks.

## 5) Acceptance Mapping
- [x] rate-limit 노이즈 비차단 정책 정의 및 워크플로 반영
- [x] 기능 검증 기준(스모크)과 배포 신호(프리뷰) 분리
- [x] PR/운영 문서에 증빙 규칙 반영
