# SplitBuddy — Go‑Live Plan

A concise, ordered checklist to take your backend live. Work top‑to‑bottom and mark each item done; share status and I’ll drive the next step.

## Top-level checklist (in order)
- Supabase: schema, keys, storage, SMTP
- Environment variables: prepare per service
- Deploy 4 services to Railway
- Domains + SSL (Railway first, then custom)
- Frontend wiring (CORS aligned)
- Push notifications (FCM) [optional]
- Hardening + observability

---

## 1) Supabase (prep)

### Keys and project
- Obtain and store securely:
  - Project URL, anon key, service role key, DB password

### Schema and indexes
- Ensure tables exist: `users`, `groups`, `group_members`, `group_invites`, `expenses`, `expense_splits`, `settlements`, `attachments`
- Ensure FKs to `auth.users` and `groups`; add indexes on key columns
- Need migration help?
  - Reply “send SQL” for a standard, safe upgrade script
  - Reply “tailor SQL” to adapt to your existing columns without duplicates

### Storage (profile pictures)
- Create bucket (e.g., `profile-pics`), public read; keep writes server-side

### Email (optional)
- Configure SMTP if you’ll send emails (invites, notifications)

---

## 2) Environment variables (per service)

### Common (all services)
- `SUPABASE_URL`, `SUPABASE_KEY` (anon)
- `FRONTEND_ORIGINS` (comma-separated exact origins; no wildcards in prod)

### Server-only (only where required)
- `SUPABASE_SECRET_KEY` (preferred) or `SUPABASE_SERVICE_KEY` (legacy) — add only to services that need elevated writes

### Auth service (8001)
- `JWT_SECRET`, `REFRESH_TOKEN_SECRET`
- `PROFILE_PIC_BUCKET` (e.g., `profile-pics`)
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM` (if emails)

### Groups (8003), Expenses (8004), AuthZ (8002)
- `SUPABASE_URL`, `SUPABASE_KEY`, `FRONTEND_ORIGINS`
- Add `SUPABASE_SECRET_KEY` (or `SUPABASE_SERVICE_KEY`) only if the code requires it

---

## 3) Railway deploy (four services)

### Create services
- Create 4 Railway services from your GitHub repo, one per folder:
  - `UserAuthentication` → port 8001
  - `UserAuthorisation` → port 8002
  - `UserGroupManagement` → port 8003
  - `ExpenseManagement` → port 8004
- Use the Dockerfile in each folder (Railway auto-detects)
- Set each service’s environment variables from Step 2
- Ensure each app binds to `0.0.0.0:$PORT`

### Quick verification
- Open each service OpenAPI: `https://<service>.railway.app/openapi.json`
- Test auth flow on 8001:
  - `POST /signin` → get access token
  - `GET /users/me` with `Authorization: Bearer <access_token>`

---

## 4) Domains + SSL
- Keep Railway subdomains (already HTTPS) or add custom domains per service
  - Add domain in Railway → create CNAME in DNS → SSL auto-provisions
- Optional: one “gateway” domain (e.g., `api.yourdomain.com`) that routes to services by path (`/auth`, `/groups`, `/expenses`) via NGINX or a tiny FastAPI proxy

---

## 5) Frontend wiring (MVP)
- Choose stack: React + Vite + Tailwind (web) or Flutter (mobile)
- Minimum pages:
  - Auth: Signup, Login, Profile
  - Groups: My Groups, Group Detail (members, invites)
  - Expenses: List, Add/Edit, Split/Preview, Balances, Settle
- Integrations:
  - Base URLs = your Railway URLs (or gateway)
  - Store access token in memory; refresh via `/token/refresh`
  - Backend CORS set to your exact frontend origin(s)

---

## 6) Push notifications (optional)
- Create Firebase project (Web or mobile configs)
- Backend:
  - Add `FCM_SERVER_KEY` to the service that sends notifications
  - Endpoints: `POST /devices/register {token, platform}`, `POST /notify` (restricted)
- Frontend:
  - Obtain FCM token, call `/devices/register` after login

---

## 7) Production hardening + observability

### Security
- Exact CORS; no wildcards
- Keep service role key server-only
- Short access token TTL (~30m); consider refresh rotation later

### Performance
- Ensure indexes on:
  - `group_members(group_id, user_id)`
  - `expenses(group_id, date)`, `expenses(paid_by)`
  - `expense_splits(expense_id, user_id)`
  - `settlements(group_id)`, `settlements(payer_id)`, `settlements(payee_id)`
  - `attachments(expense_id)`

### Ops
- DB backups (Supabase default) with sensible retention
- Error tracking (e.g., Sentry), request logs, simple dashboards (P95, error rate)

### Future
- Add RLS policies once traffic stabilizes

---

## Immediate next actions
- Tell me:
  - “send SQL” or “tailor SQL” for the Supabase schema
  - Which Supabase keys and bucket name you’ve set
  - When the 4 Railway services are up and their URLs
- After you share URLs, I will:
  - Lock down CORS precisely
  - Add optional `/health` endpoints
  - (Optional) Add FCM device endpoints
