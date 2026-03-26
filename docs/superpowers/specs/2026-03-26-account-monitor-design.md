# Account Monitor Phase 1 Design

**Goal**

Add a conservative account-monitoring loop for the existing registration system. The first phase should only do three things: scheduled health checks, manual trigger, and low-inventory auto-registration. It must reuse existing refresh, validate, subscription-check, registration, and CPA upload flows instead of introducing a new external probing API.

**Scope**

- Add persistent monitor configuration to existing settings storage.
- Add a backend scheduler that can run on startup and on demand.
- Emit monitor system logs that can be polled by the registration page.
- Trigger batch registration automatically when healthy accounts fall below a threshold.
- Add registration-page controls for monitor status, configuration, and manual trigger.

**Non-Goals**

- No automatic deletion from CPA / CLIProxy.
- No new dedicated credential-health API against `wham/usage`.
- No separate database tables for monitor tasks.
- No aggressive cleanup of local accounts beyond existing token refresh / validation status updates.

**Health Check Definition**

Phase 1 uses existing project semantics:

1. Refresh tokens for selected candidate accounts when possible.
2. Validate current `access_token`.
3. Optionally check subscription type using the existing payment route logic.
4. Treat accounts with valid tokens as healthy inventory.

This keeps health checks aligned with the rest of the codebase and avoids binding the system to unstable external probing endpoints.

**Scheduling Model**

Create a lightweight in-process scheduler that starts with FastAPI startup. It sleeps for a configured interval in minutes, skips overlapping runs, and supports manual trigger. Logs are stored in memory with a monotonic counter so the registration page can poll incrementally.

**Auto-Registration Model**

After each monitor run, compute healthy inventory count from the database. If healthy count is below a configured threshold and auto-registration is enabled, create a new batch registration run using existing registration code. Configuration should reuse the registration page’s selected email service and CPA auto-upload settings.

**UI Model**

Add a compact “账号体检与补货” block to the registration page:

- enable/disable scheduled monitor
- interval minutes
- per-account sleep seconds
- enable/disable auto-registration
- healthy inventory threshold
- batch replenish count
- status badge
- save/apply button
- manual trigger button

The monitor writes into the existing console panel as system log lines.

**Error Handling**

- Skip overlapping runs and log the skip.
- Continue across per-account failures; never abort the full run because one account fails.
- On unexpected monitor exceptions, emit error logs and keep the scheduler loop alive.
- If auto-registration cannot be queued, log the failure and finish the monitor run.

**Testing**

- Scheduler config API round-trip.
- Manual trigger endpoint invokes the monitor job and returns logs.
- Auto-registration trigger fires when healthy inventory is below threshold.
- No auto-registration when inventory is above threshold.
- Startup remains compatible and existing registration tests stay green.
