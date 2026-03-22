# CLAUDE.md

## Project Overview

codex-register v2 - OpenAI account batch registration & management system with a FastAPI web UI.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt
# or: uv pip install -r requirements.txt

# Run
python webui.py --port 8000
```

Default password: `admin123` (change via `APP_ACCESS_PASSWORD` env var or `--access-password` flag).

## Project Structure

- `webui.py` — Entry point (FastAPI + Uvicorn)
- `src/core/register.py` — **Registration engine** (the main flow orchestrator)
- `src/core/openai/oauth.py` — OAuth/PKCE flow
- `src/core/openai/token_refresh.py` — Token refresh
- `src/core/openai/payment.py` — Payment/subscription
- `src/core/http_client.py` — HTTP client (curl_cffi with browser fingerprint)
- `src/config/constants.py` — API endpoints, page types, defaults
- `src/config/settings.py` — Database-backed settings (Pydantic)
- `src/database/` — SQLAlchemy ORM models, CRUD, session management
- `src/services/` — Email service implementations (Tempmail, Outlook, MoeMail, DuckMail, FreeMail, IMAP)
- `src/web/` — FastAPI routes, WebSocket, task manager
- `templates/` — Jinja2 HTML pages
- `static/` — CSS + vanilla JS frontend

## Registration Flow (register.py `run()`)

**Steps 1-12: Registration**
1. Check IP geolocation
2. Create email (via email service)
3. Init session
4. Start OAuth (generate auth_url with PKCE)
5. Get Device ID (visit auth_url → oai-did cookie)
6. Sentinel check
7. Submit signup form (`authorize/continue`)
8. Register password (`user/register`) [skip if existing account]
9. Send OTP (`email-otp/send`) [skip if existing account]
10. Get verification code from email
11. Validate OTP (`email-otp/validate`)
12. Create account (`create_account`) [skip if existing account]

**Step 12.5: Fresh session login flow (new accounts only)**

OpenAI's registration flow now requires phone verification (`add_phone`) after create_account, which blocks workspace creation. The workaround is to create a brand new HTTP session and complete a full login flow, which bypasses the phone requirement:

- 12.5a: New OAuth URL (new state + code_verifier)
- 12.5b: New Device ID
- 12.5c: Sentinel check
- 12.5d: Submit email with `screen_hint: "login"` → `login_password`
- 12.5e: `password/verify` endpoint with registered password → `email_otp_verification`
- 12.5f: Receive new OTP from email
- 12.5g: Validate OTP → `consent` page
- 12.5h: Get Workspace ID from cookie
- 12.5i: Select Workspace
- 12.5j: Follow redirect chain → callback URL
- 12.5k: OAuth token exchange → done

**Steps 13-16: For existing accounts (login path)**
13. Get Workspace ID (from `oai-client-auth-session` cookie JWT)
14. Select Workspace
15. Follow redirect chain → find callback URL
16. OAuth callback → exchange code for tokens

## Key Technical Details

- HTTP client uses `curl_cffi` for browser fingerprint impersonation
- OAuth uses PKCE (S256 code challenge)
- Session cookies are shared across the entire flow via `self.session`
- `_otp_sent_at` timestamp is used to filter old OTP emails when receiving verification codes
- `_is_existing_account` flag controls which steps to skip for already-registered emails
- Concurrency: ThreadPoolExecutor (max 50 workers) + asyncio Semaphore
- **New account login flow uses a completely fresh session** — the registration session's cookies interfere with the login flow, so a new `OpenAIHTTPClient` + new OAuth URL is required
- `password/verify` endpoint (`/api/accounts/password/verify`) accepts only `{"password": "..."}` (no username) — the session context determines the user

## Testing

```bash
pytest tests/
```

## Key API Endpoints (constants.py)

- `sentinel`: `https://sentinel.openai.com/backend-api/sentinel/req`
- `signup`: `https://auth.openai.com/api/accounts/authorize/continue`
- `register`: `https://auth.openai.com/api/accounts/user/register`
- `password/verify`: `https://auth.openai.com/api/accounts/password/verify` (login only, accepts `{"password": "..."}`)
- `send_otp`: `https://auth.openai.com/api/accounts/email-otp/send`
- `validate_otp`: `https://auth.openai.com/api/accounts/email-otp/validate`
- `create_account`: `https://auth.openai.com/api/accounts/create_account`
- `select_workspace`: `https://auth.openai.com/api/accounts/workspace/select`

## Language

Code comments, logs, and UI are in Chinese (zh-CN). Keep this convention.
