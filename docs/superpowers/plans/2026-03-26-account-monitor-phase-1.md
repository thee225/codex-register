# Account Monitor Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add scheduled account health checks, manual trigger, and low-inventory auto-registration on top of the existing registration system.

**Architecture:** Persist monitor config in the existing settings store, run an in-process scheduler from FastAPI startup, reuse current account refresh/validate/subscription logic for health checks, and queue replenishment through the existing batch registration pipeline. Surface monitor state and logs on the registration page.

**Tech Stack:** FastAPI, existing settings storage, existing registration/task manager code, vanilla JS frontend, pytest

---

### Task 1: Add Config Surface

**Files:**
- Modify: `src/config/settings.py`
- Modify: `src/web/routes/settings.py`
- Test: `tests/test_account_monitor.py`

- [ ] **Step 1: Write the failing test**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Add settings fields and API payload support**
- [ ] **Step 4: Run test to verify it passes**

### Task 2: Add Monitor Scheduler Backend

**Files:**
- Create: `src/core/account_monitor.py`
- Create: `src/web/routes/account_monitor.py`
- Modify: `src/web/routes/__init__.py`
- Modify: `src/web/app.py`
- Test: `tests/test_account_monitor.py`

- [ ] **Step 1: Write the failing tests for manual trigger and low-inventory auto-registration**
- [ ] **Step 2: Run tests to verify they fail**
- [ ] **Step 3: Implement scheduler, logs, trigger endpoint, and startup hook**
- [ ] **Step 4: Run targeted tests to verify they pass**

### Task 3: Add Registration Page Controls

**Files:**
- Modify: `templates/index.html`
- Modify: `static/js/app.js`
- Test: `tests/test_static_asset_versioning.py`

- [ ] **Step 1: Write/adjust the failing frontend-facing regression test if needed**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Add monitor config block, status badge, save/apply, and manual trigger wiring**
- [ ] **Step 4: Run targeted tests to verify they pass**

### Task 4: Verify

**Files:**
- Modify: `docs/superpowers/specs/2026-03-26-account-monitor-design.md`
- Modify: `docs/superpowers/plans/2026-03-26-account-monitor-phase-1.md`

- [ ] **Step 1: Run targeted tests**
  Run: `uv run pytest -q tests/test_account_monitor.py tests/test_static_asset_versioning.py`
- [ ] **Step 2: Run full suite**
  Run: `uv run pytest -q`
- [ ] **Step 3: Review git diff and status**
  Run: `git status --short`
- [ ] **Step 4: Commit**
  Run: `git add ... && git commit -m "feat: add account monitor phase 1"`
