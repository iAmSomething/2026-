# 2026-02-27 Scope Title Intent Leak Runtime Guard Report

## 1) Scope
- Issue: #480
- Goal: Prevent local matchup/map responses from exposing mismatched metro-level article context.

## 2) Implemented Guards
- Matchup response guard (`GET /api/v1/matchups/{matchup_id}`)
  - If `office_type/region_code` conflicts with `article_title` intent, `article_title` is masked to `null`.
- Map latest guard (`GET /api/v1/dashboard/map-latest`)
  - Added exclusion reason: `scope_title_intent_leak`.
  - Rows with title intent mismatch are excluded from response items.
  - `title` remains canonical-first via existing canonical normalization policy.

## 3) Detection Rule
- Intent keywords mapped to broad region prefixes (e.g. `서울시장`, `부산시장`, `인천시장`, `...도지사`).
- Local office (`기초*`) with metro/provincial-intent keyword is treated as leak.
- Non-local rows are treated as leak when title intent region prefix != row region prefix.

## 4) Files Changed
- `app/api/routes.py`
- `tests/test_api_routes.py`
- `docs/02_DATA_MODEL_AND_NORMALIZATION.md`

## 5) Verification
- Command:
  - `/Users/gimtaehun/election2026_codex/.venv/bin/python -m pytest -q tests/test_api_routes.py -k "map_latest_excludes_scope_title_intent_leak_rows or matchup_masks_scope_title_intent_leak_for_local_matchup or map_latest_sanity_filter_drops_invalid_candidate_and_legacy_title_rows"`
- Result:
  - `3 passed`

## 6) Acceptance Mapping
- [x] `/api/v1/matchups/2026_local|기초자치단체장|26-710` leak title masked (`article_title=null`)
- [x] `/api/v1/dashboard/map-latest` `region_code=28-450` leak row excluded (`scope_title_intent_leak`)
- [x] scope/title intent leak blocked at API runtime layer
