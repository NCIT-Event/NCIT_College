# Phase 1: Sign-in and access control

What Phase 1 adds, how to set it up, and how to check it works.

## What's included

| Part | Where | What it does |
|---|---|---|
| auth-service | `services/auth-service/` | Google sign-in limited to `@ncit.edu.np`, sessions (JWT + refresh token), roles, invites, Users & access API |
| audit-service | `services/audit-service/` | Records sign-ins, refused sign-ins and every access change; Audit log API |
| audit-worker | same image, `python -m app.worker` | Moves events from Redis into the audit database |
| Shared library | `libs/ncit-common/` | Token checks, role checks, CSRF protection and revocation, used by every service |
| Login page | `frontend/src/pages/login.html` | "Sign in with Google", clear error messages |
| Dashboard | `frontend/src/pages/dashboard/index.html`, `public/assets/js/dashboard.js` | Real signed-in user, menu by role, Users & access, Audit log |
| Gateway | `gateway/nginx.conf` | Routes `/api/v1/auth/` and `/api/v1/audit/`, rate-limits sign-in |

## How sign-in works

1. The user clicks **Sign in with Google** and chooses their account.
2. Google sends them back to `/api/v1/auth/google/callback`. auth-service verifies Google's signed ID token and accepts it only if **all** of these hold:
   - Google says the email is verified;
   - the Workspace domain claim (`hd`) is `ncit.edu.np`;
   - the email address ends with `@ncit.edu.np`.
   A Gmail account, or a personal Google account registered with a college address, is refused and the refusal is logged.
3. auth-service sets three cookies:
   - `ncit_access`: a JWT, valid 15 minutes, HttpOnly;
   - `ncit_refresh`: valid 7 days, HttpOnly, sent only to `/api/v1/auth`, replaced on every use;
   - `ncit_csrf`: a random value the page sends back in the `X-CSRF-Token` header on every change.
4. Other services check the JWT locally with the public key; there is no call to auth-service per request.

**Revoking access:** removing a role, suspending a user or signing out takes effect on the user's **next request**, not after 15 minutes. auth-service writes a revocation entry to Redis, which every service checks. The dashboard then gets a fresh token, with the reduced roles, automatically.

**First sign-in:** users invited from the dashboard get exactly the roles granted to them. Anyone else with an `@ncit.edu.np` account gets `DEFAULT_ROLE` (Student). Emails listed in `SUPER_ADMIN_EMAILS` become Super Admin on their first sign-in.

**Safeguards:** at least one Super Admin must always remain, and nobody can suspend themselves or remove their own Super Admin role. Reusing a stolen refresh token ends that whole sign-in.

---

## Setup

### 1. Create the Google OAuth client (once, by an NCIT Google Workspace admin)

1. Go to <https://console.cloud.google.com/> and sign in with an NCIT admin account. Create a project, e.g. **NCIT Website**.
2. **APIs & Services → OAuth consent screen**
   - User type: **Internal**. Google then only lets `@ncit.edu.np` accounts through, a second layer on top of the website's own check.
   - App name: *NCIT Website*; support email: the IT office address; authorised domain: your site's domain.
   - Scopes: `openid`, `email`, `profile` (the defaults).
3. **APIs & Services → Credentials → Create credentials → OAuth client ID**
   - Application type: **Web application**.
   - **Authorised redirect URIs**, one per environment, exactly:
     - `http://localhost:8080/api/v1/auth/google/callback` (local)
     - `https://staging.ncit.edu.np/api/v1/auth/google/callback` (staging, if used)
     - `https://www.ncit.edu.np/api/v1/auth/google/callback` (production; use the real domain)
4. Copy the **Client ID** and **Client secret** into `.env` (next step). Treat the secret like a password.

### 2. Create `.env`

```bash
pip install cryptography          # once
python3 infra/setup_env.py        # writes .env with fresh keys and database passwords
```

Then edit `.env`:

| Variable | Set to |
|---|---|
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | From step 1 |
| `OAUTH_REDIRECT_URI` | The redirect URI for this environment, exactly as entered in Google |
| `SUPER_ADMIN_EMAILS` | The first Super Admins, comma-separated, e.g. `principal@ncit.edu.np,it.head@ncit.edu.np`. Use at least two. |
| `COOKIE_SECURE` | `false` only for `http://localhost`; **`true` on staging and production (https)** |
| `DEV_LOGIN` | `false`. Set `true` only on your own computer to test without Google; the service refuses to start with it while `COOKIE_SECURE=true`. |

`.env` is in `.gitignore`. Never commit it. Running `setup_env.py --force` creates new keys, which signs everyone out.

### 3. Start the stack

```bash
docker compose -f infra/docker-compose.yml --env-file .env up --build
```

Open <http://localhost:8080/login.html>. Database tables are created automatically on start (`alembic upgrade head`).

**Without Google credentials (local testing):** set `DEV_LOGIN=true` and `COOKIE_SECURE=false`. The login page then shows a "Development only" form where you can sign in as any `@ncit.edu.np` address.

**Front end only (no backend):** `cd frontend && npm run serve` still works. The dashboard detects there is no backend and opens in a labelled **demo mode** with sample people.

### 4. Production checklist

- [ ] HTTPS in front of the gateway (e.g. Caddy, or Nginx with Let's Encrypt), and `COOKIE_SECURE=true`
- [ ] `DEV_LOGIN=false`
- [ ] OAuth consent screen set to **Internal**
- [ ] Production redirect URI added in Google and set in `OAUTH_REDIRECT_URI`
- [ ] At least two people in `SUPER_ADMIN_EMAILS`
- [ ] `.env` readable only by the deploy user (`chmod 600 .env`)
- [ ] Nightly Postgres backups (both `ncit_auth` and `ncit_audit`)

---

## Using it

- **Grant a role:** Dashboard → Users & access → **Grant a role**. Enter an `@ncit.edu.np` email, choose the role (and the department for a Head of Department), and optionally an expiry date. People who haven't signed in yet are listed as *Invited* and get the role on their first sign-in.
- **Remove a role:** click the **×** on the role chip. **Undo** appears for a few seconds.
- **Suspend:** the account is signed out everywhere at once and can't sign in again until reactivated.
- **Bulk import:** **Import CSV** with the columns `email,role,department,expires`, for example:
  ```csv
  email,role,department,expires
  ram.sharma@ncit.edu.np,teacher,,
  sita.kc@ncit.edu.np,hod,computer,2027-12-31
  ```
  Role can be the code (`hod`) or the name (`Head of Department`). Department codes: `computer`, `it`, `software`, `ice`, `civil`, `architecture`, `bca`, `management`. Each row is reported as granted or failed, with the reason.
- **Audit log:** Dashboard → Audit log. Search by email and filter by sign-ins, refused sign-ins, role changes or suspensions.
- **Emergency Super Admin** (for example, if everyone lost access): on the server, run
  `docker compose -f infra/docker-compose.yml exec auth-service flask --app wsgi grant-super-admin someone@ncit.edu.np`

---

## Phase 1 gate: how it was checked

| Gate | Automated test | End-to-end check (real Postgres, Redis, nginx, browser) |
|---|---|---|
| Outside emails are refused | `test_outside_email_is_refused`, `test_college_address_without_workspace_claim_is_refused`, `test_lookalike_domain_is_refused` | Signing in as `someone@gmail.com` shows the refusal message; the audit log records "Sign-in refused: not an NCIT account" |
| A revoked role loses access immediately | `test_revoked_role_stops_working_immediately` | HOD granted, signs in, role removed: the HOD's old token is rejected (`401 token_revoked`) on its next use; after reload the HOD has no dashboard role |
| Each HOD edits only their department | `test_hod_edits_own_department_only` (shared library) | The HOD's menu shows only their own modules; opening `#users` falls back to Overview |
| Changes are audited | `test_store_event_is_idempotent`, `test_worker_consumes_stream` | Grant, revoke, sign-in and refused sign-in all appear in the Audit log |

Run the tests:

```bash
pip install -e "libs/ncit-common[dev]"
pip install -r services/auth-service/requirements.txt -r services/audit-service/requirements.txt
(cd libs/ncit-common && pytest -q)
(cd services/auth-service && pytest -q)
(cd services/audit-service && TEST_REDIS_URL=redis://localhost:6379/15 pytest -q)
```

## API reference (through the gateway)

| Method & path | Who | Purpose |
|---|---|---|
| `GET /api/v1/auth/config` | anyone | Whether Google and dev sign-in are available; the allowed domain |
| `GET /api/v1/auth/google/login?next=/dashboard/` | anyone | Starts Google sign-in |
| `GET /api/v1/auth/google/callback` | Google | Finishes sign-in, sets cookies |
| `POST /api/v1/auth/refresh` | signed in | New access token (rotates the refresh token) |
| `POST /api/v1/auth/logout` | signed in | Signs out this browser |
| `GET /api/v1/auth/me` | signed in | Current user and roles |
| `GET /api/v1/auth/roles` | signed in | Role and department catalogue |
| `GET /api/v1/auth/.well-known/jwks.json` | anyone | Public key for verifying tokens |
| `GET /api/v1/auth/users?q=&role=&status=&page=` | Super Admin | List and search users |
| `GET /api/v1/auth/users/summary` | Super Admin | Counts for "Needs your attention" |
| `POST /api/v1/auth/users/grants` | Super Admin | Grant `{email, role, scope?, expires_at?}` |
| `DELETE /api/v1/auth/users/{id}/grants/{grant_id}` | Super Admin | Remove a role |
| `POST /api/v1/auth/users/{id}/suspend` / `reactivate` | Super Admin | Suspend or restore an account |
| `POST /api/v1/auth/users/import` | Super Admin | CSV bulk grant |
| `GET /api/v1/audit/?q=&type=&page=` | Super Admin | Audit entries, newest first |

All state-changing requests from the browser must send `X-CSRF-Token` (the `ncit_csrf` cookie value); the dashboard does this automatically.
