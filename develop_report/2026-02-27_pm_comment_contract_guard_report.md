# 2026-02-27 PM Comment Contract Guard Report

## 1) Scope
- Issue: #489
- Goal: Ensure PM/automation comment schema always includes required keys (`decision:`, `next_status:`).

## 2) Implemented
1. Comment template utility
- Added `scripts/pm/comment_template.sh`.
- Supports:
  - auto-insert missing PM contract keys
  - `--validate-only` schema validation mode

2. PM Cycle hardening
- Updated `scripts/pm/pm_cycle_dry_run.sh` to:
  - build issue comment via `comment_template.sh`
  - run pre-post validation (`--validate-only`)
  - skip comment post with warning if validation fails

3. Workflow wiring
- Updated `.github/workflows/pm-cycle-dry-run.yml` to ensure template script executable in CI.

4. Documentation
- Added PM comment contract section and usage examples in `docs/08_ROLE_BASED_GIT_WORK_SYSTEM_GUIDE.md`.

## 3) Files Changed
- `scripts/pm/comment_template.sh`
- `scripts/pm/pm_cycle_dry_run.sh`
- `.github/workflows/pm-cycle-dry-run.yml`
- `docs/08_ROLE_BASED_GIT_WORK_SYSTEM_GUIDE.md`
- `tests/test_pm_comment_template_script.py`

## 4) Verification
- Shell syntax check:
  - `bash -n scripts/pm/comment_template.sh`
  - `bash -n scripts/pm/pm_cycle_dry_run.sh`
- Test:
  - `/Users/gimtaehun/election2026_codex/.venv/bin/python -m pytest -q tests/test_pm_comment_template_script.py`
  - result: `3 passed`

## 5) Acceptance Mapping
- [x] PM comment required keys auto-insert guard implemented.
- [x] PM cycle comment post now has pre-schema validation and fail-safe skip.
- [x] Contract usage documented with concrete command examples.
