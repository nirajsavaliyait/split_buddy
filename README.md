# SplitBuddy Backend (Beginner-Friendly)

FastAPI microservices for auth, authorization, groups, and expenses.

## Services
- 8001 UserAuthentication (Auth)
- 8002 UserAuthorisation (AuthZ)
- 8003 UserGroupManagement (Groups)
- 8004 ExpenseManagement (Expenses)

## Quick run
- Requirements: Python 3.11+, virtualenv, Supabase URL/KEY in each service `.env`.
- In four terminals, run:
  - uvicorn UserAuthentication.main:app --reload --port 8001
  - uvicorn UserAuthorisation.main:app --reload --port 8002
  - uvicorn UserGroupManagement.main:app --reload --port 8003
  - uvicorn ExpenseManagement.main:app --reload --port 8004
- Health: `python smoke_test.py` (checks imports + OpenAPI)

## Auth (8001)
- POST /signup
- POST /signin
- POST /login (alias of /signin)
- POST /token/refresh
- GET /verify-email
- POST /forgot-password
- POST /reset-password
- GET /users/me
- PUT /users/me
- POST /users/me/profile-picture
- GET /users/me/profile-picture
- DELETE /users/me/profile-picture

## AuthZ (8002)
- GET /auth/introspect
- GET /authz/groups/{group_id}/is-member
- GET /authz/groups/{group_id}/is-owner
- GET /authz/expenses/{expense_id}/in-group

## Groups (8003)
- POST /groups
- PUT /groups/{group_id}
- DELETE /groups/{group_id}
- GET /groups
- GET /groups/paged
- GET /groups/{group_id}/members
- POST /groups/{group_id}/invites
- GET /groups/{group_id}/invites (owner-only)
- POST /groups/{group_id}/invitations/respond
- POST /groups/{group_id}/members/{user_id}/relationship-tag
- POST /groups/{group_id}/members/{user_id}/role
- DELETE /groups/{group_id}/members/{user_id}
- GET /groups/{group_id}/audit-log (stub)
- GET /groups/search
- POST /contacts/import (10-digit phones)
- GET /users/lookup?phone= (accepts 10-digit or +91 + 10-digit)
- POST /groups/{group_id}/members/by-phone

## Expenses (8004)
- POST /groups/{group_id}/expenses  (body: { description, amount })
- GET /expenses/{expense_id}
- PATCH /expenses/{expense_id}
- DELETE /expenses/{expense_id}
- GET /groups/{group_id}/expenses  (paged, sort by date asc/desc)
- GET /users/{user_id}/expenses
- POST /expenses/{expense_id}/splits (legacy add)
- GET /expenses/{expense_id}/splits
- POST /expenses/{expense_id}/split/preview
- PUT /expenses/{expense_id}/split
- GET /groups/{group_id}/balances
- GET /users/{user_id}/balances[?group_id=]
- POST /groups/{group_id}/settlements/suggest
- POST /groups/{group_id}/settlements
- GET /groups/{group_id}/settlements
- POST /expenses/{expense_id}/attachments
- GET /expenses/{expense_id}/attachments
- GET /categories
- GET /reports/groups/{group_id}/summary
- GET /reports/groups/{group_id}/summary.csv
- GET /reports/groups/{group_id}/summary.pdf
- GET /reports/users/{user_id}/monthly?month=
- GET /reports/users/{user_id}/summary.csv
- GET /reports/users/{user_id}/summary.pdf

## Deploying to Railway
- For each service folder (UserAuthentication, UserAuthorisation, UserGroupManagement, ExpenseManagement):
  - Create a new Railway service from your GitHub repo, set the root to that service folder.
  - Railway will detect the Dockerfile.
  - Set environment variables from the corresponding .env.example.
  - Expose the service port (8001–8004). Railway provides HTTPS and a subdomain automatically.
- Custom domain + SSL:
  - Add a custom domain in Railway for each service you want public; Railway issues SSL via Let’s Encrypt.
  - Or front services with an API gateway or reverse proxy under one domain.

## Push notifications (FCM)
- For mobile/web clients:
  - Create a Firebase project, enable Cloud Messaging, download client config (google-services.json or web SDK keys).
  - Store FCM server key as a secret (e.g., FCM_SERVER_KEY) in the service that will send notifications.
  - Add an endpoint to register device tokens and send notifications (future work).

## Frontend guidance
- Start with a simple web UI (React + Vite) or mobile (Flutter/React Native).
- Connect to these APIs via HTTPS; store JWT in memory and refresh as needed.
- Keep UI components modular so future features slot in without redesign.

## Notes
- JWT: Authorization: Bearer <token> across services.
- Supabase: local authz checks in 8003/8004; 8002 provides helper checks.
- Group phones are 10-digit only; lookups accept 10-digit and +91 variants.
- Expense create only needs `description` and `amount`; defaults set server-side and schema mismatches handled gracefully.
