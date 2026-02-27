# 2026-02-27 Dashboard Summary Single-Set Policy Report

## 1) Scope
- Issue: #479
- Goal: Fix `GET /api/v1/dashboard/summary` to enforce single-card-set selection per option and expose explicit selection contract fields.

## 2) Changes
- Summary response root field added:
  - `selection_policy_version = "summary_single_set_v1"`
- Summary card field added:
  - `selected_reason` (`official_preferred` | `latest_fallback`)
- Summary selection policy fixed to:
  1. `official_confirmed` desc
  2. `source_grade` desc
  3. `published_at` desc (`official_release_at` fallback to `article_published_at`)
  4. `updated_at` desc (`observation_updated_at`)
- Selection trace now includes `selection_policy_version`.
- Repository summary query ranking aligned to option-level partition:
  - partition key: `option_type + option_name + audience_scope`
  - tie-break aligned with the fixed policy above.

## 3) Files Changed
- `app/api/routes.py`
- `app/models/schemas.py`
- `app/services/repository.py`
- `tests/test_api_routes.py`
- `tests/test_repository_dashboard_summary_scope.py`
- `docs/02_DATA_MODEL_AND_NORMALIZATION.md`
- `docs/03_UI_UX_SPEC.md`

## 4) Verification
- Command:
  - `/Users/gimtaehun/election2026_codex/.venv/bin/python -m pytest -q tests/test_api_routes.py tests/test_repository_dashboard_summary_scope.py tests/test_repository_read_cache.py -k "dashboard_summary"`
- Result:
  - `9 passed, 31 deselected`

## 5) Acceptance Mapping
- [x] Summary card duplicate 0 by option-level representative selection.
- [x] Non-national scope excluded from summary cards (`audience_scope == national` only).
- [x] Selection rationale exposed in API (`selection_policy_version`, `selected_reason`).

## 6) Notes
- Existing legacy fields remain for backward compatibility.
- Summary policy is now explicit and traceable in response payload.
