# Launch readiness report (Phase 6)

What was tested before launch, how, the results, and what was fixed along the way. Every test here can be run again (commands are given) and should be, on the production server, once it's set up.

| Area | Result |
|---|---|
| [Docker deployment](#1-docker-deployment) | The full stack (11 services, 3 workers, PostgreSQL, Redis, gateway) builds and runs with Docker Compose; every flow works on it. Four deployment bugs were found and fixed. |
| [HTTPS](#2-https) | Caddy in front issues the certificate, redirects http, sends HSTS; the gateway can't be reached around it. |
| [Security](#3-security) | 52 of 52 automated checks pass (32 of 32 read-only checks over HTTPS). Dependency scan clean after upgrading 4 packages with known vulnerabilities. A full security review (2026-11-04) found and fixed 7 problems: [SECURITY-REVIEW.md](SECURITY-REVIEW.md). |
| [Accessibility](#4-accessibility-wcag-21-aa) | 0 WCAG 2.1 A/AA violations on 65 page states (axe); keyboard, focus, 400% zoom and reduced-motion checks pass. |
| [Load](#5-load) | ~6,700 requests per second at 100 simultaneous visitors, 0 errors, 95% of responses under 40 ms. |
| [Backup and restore](#6-backup-and-restore) | Backed up, deleted *everything*, restored: all data and private documents came back. |
| [Automated tests](#7-automated-tests) | 165 tests in 13 suites pass, on the upgraded dependencies, with deprecation warnings treated as errors. |

---

## 1. Docker deployment

**How:** `docker compose -f infra/docker-compose.yml --env-file <fresh env> up -d --build` on a clean machine, with a `.env` made by `python3 infra/setup_env.py --output …`. Then the same browser tests used for Phases 4–6 were run against it (applying for admission with an emailed code, a job application, alumni registration, events and clubs, contact, search), and the security suite.

**Bugs found and fixed.** None of these showed up when running the services directly; all four would have hit the live server:

| Bug | Effect | Fix |
|---|---|---|
| The database container only received the passwords of the first 4 services | The 7 services added in Phases 4–6 couldn't connect to their databases and restarted in a loop | All passwords passed to it |
| PostgreSQL creates databases only on the very first start of an empty volume | A service added after launch would never get its database | The database script is now safe to re-run, and a one-off `db-setup` container runs it on every `docker compose up`, before the services start. Verified: on a server that already had 4 databases it created the 7 missing ones. |
| nginx looked up each service's address once, at start-up | After a service container was recreated (an update, or a restart after a crash), the gateway sent its traffic to whichever container had picked up the old address. In the test, event requests reached another service. | Upstreams re-resolve through Docker's DNS every 5 seconds (`resolve`, nginx 1.27.5 pinned). Verified by recreating services while running: routing stayed correct. |
| Workers started before their service had created its tables, and inherited a web health check | The search worker crashed until restarted; workers showed as "unhealthy" | Workers wait for their service to be healthy; the web health check is disabled for workers |

Also changed for deployment: the public port is configurable (`HTTP_PORT`), and `setup_env.py --output` writes a settings file for another environment (e.g. staging).

*Test-environment note:* the build machine intercepts HTTPS, so for this test only the Python base image was given that machine's certificate, and images came from Google's Docker Hub mirror after Docker Hub rate-limited the machine. Production servers use the official images unchanged.

## 2. HTTPS

`infra/docker-compose.tls.yml` adds [Caddy](https://caddyserver.com/) in front of the gateway. It gets and renews a Let's Encrypt certificate for `SITE_DOMAIN` automatically. Tested with production settings (`COOKIE_SECURE=true`, `DEV_LOGIN=false`) and a locally issued certificate:

- `http://…/about` → `308` redirect to `https://…/about`
- `Strict-Transport-Security: max-age=31536000; includeSubDomains` sent over HTTPS only
- the gateway's own port is closed: the only way in is through Caddy
- the development sign-in returns "not found"
- `tools/security_check.py https://…`: **32 of 32 passed**

## 3. Security

### Automated security checks

`python3 tools/security_check.py <site> [--dev]` covers:

- **Headers:** security headers on pages, APIs, static files, errors.
- **Hidden things:** no server version; `.env`, `.git`, source and private folders not served; path traversal refused.
- **Access:** sign-in required on 13 protected APIs; forged tokens (`alg: none`, wrong key) refused.
- **Private files:** application documents unreachable by URL.
- **Bad input:** injection-shaped input handled; errors returned as plain JSON with no internals.
- **Rate limits:** sign-in codes are rate limited.
- **With `--dev`** (local only):
  - **cookies:** HttpOnly and SameSite flags;
  - **CSRF:** a missing or wrong token is refused;
  - **role separation:** 8 roles (content, events, ECA, admissions, HR, alumni, HOD, student) are each refused by the other areas' APIs;
  - **uploads:** disguised uploads (HTML or PDF named `.jpg`) are refused;
  - **redirects and codes:** no open redirect; college addresses can't use email codes;
  - **outsider accounts:** an applicant account can't register for events or join clubs;
  - **visitor address:** a faked `X-Forwarded-For` never reaches the audit log.

**Result:** 52 of 52 on the local stack (3 more since 2026-11-04 for notifications and the page cache); 32 of 32 read-only checks over HTTPS on Docker.

The full security review, with the attacks tried and the 7 problems fixed, is in [SECURITY-REVIEW.md](SECURITY-REVIEW.md).

**Hardening done in this phase:**
- **Security headers on every response.** nginx silently drops server-level headers in any location that adds its own, so the API and file responses had *no* security policy. All location-level `add_header` lines were removed; one set now applies everywhere:
  - **Content-Security-Policy:** `default-src 'self'`, no inline scripts, no plug-ins or framing, forms only to this site;
  - **X-Frame-Options**, **X-Content-Type-Options**, **Referrer-Policy**;
  - **Permissions-Policy:** no camera, microphone, location or payment;
  - **Cross-Origin-Opener-Policy**;
  - **HSTS**, over HTTPS only.
- Request size limited to 1 MB except on upload routes; slow-request timeouts set.
- Contact form: rate limited, a hidden spam trap, and it never emails the address typed in, so it can't be used to send mail to strangers.

### Dependencies

`pip-audit` against every service's requirements found published vulnerabilities in four pinned packages. They were upgraded and every test suite passes on the new versions:

| Package | Was | Now | Advisories fixed |
|---|---|---|---|
| Pillow (image handling) | 11.0.0 | 13.0.0 | 68 |
| PyJWT (sign-in tokens) | 2.10.1 | 2.15.1 | 22 |
| Flask | 3.1.0 | 3.1.3 | 4 |
| requests | 2.32.3 | 2.34.2 | 4 |

SQLAlchemy, psycopg and alembic were moved to their latest patch releases. `npm audit` on the front end: 0 vulnerabilities. A static security scan of the code (`ruff --select S`) found only false positives.

**Kept up to date automatically:** CI now runs `pip-audit` and `npm audit` on every change **and weekly**, so a newly published vulnerability fails the build even when nobody has touched the code.

## 4. Accessibility (WCAG 2.1 AA)

**Automated:** the axe engine (rules tagged WCAG 2.0/2.1 A and AA) ran on:

- 24 public pages at desktop and phone size;
- 16 dashboard screens;
- an open editor panel.

That's 65 page states in total. The first run found 2 problems, both in the details box on event and club pages (`<dt>`/`<dd>` wrapped in extra elements, so screen readers couldn't pair labels and values). After fixing them: **0 violations**.

**By hand (scripted keyboard tests):**
- The first Tab goes to "Skip to content", and Enter jumps to the main content.
- Every one of the first 25 Tab stops shows a visible focus outline (2 px).
- The search panel opens with Enter and puts focus in the search box; Escape closes it and returns focus to the button. Dashboard panels behave the same way.
- **400% zoom** (a 320 px-wide viewport): no sideways scrolling on the home page, apply, events, contact, search and department pages, after fixing the event tabs, which overflowed by 9 px.
- With **reduced motion** on, the home page banner doesn't move by itself.

The public [Accessibility statement](/accessibility) describes this and how to report problems.

## 5. Load

`python3 tools/load_test.py <site> --users 10,50,100 --seconds 30` simulates visitors browsing a realistic mix:

- home page and its data, department pages, news, notices, events, clubs, admissions, and static files;
- searches, half of them unique so they bypass the cache and reach the database.

| Visitors at once | Requests | Requests/s | Median | 95th percentile | 99th percentile | Errors |
|---|---|---|---|---|---|---|
| 10 | 166,685 | 5,556 | 1 ms | 7 ms | 17 ms | 0 |
| 50 | 199,429 | 6,648 | 5 ms | 23 ms | 58 ms | 0 |
| 100 | 201,387 | 6,713 | 13 ms | 39 ms | 69 ms | 0 |

This was on one 4-core machine, which ran both the site and the load generator, so the figures are conservative. For scale, even admission-results day for a college this size is likely to be in the tens of requests per second. Public pages are cached (in Redis by each service since 2026-11-04, see [CACHING-AND-NOTIFICATIONS.md](CACHING-AND-NOTIFICATIONS.md), plus 5 seconds at the gateway), which takes most of the load; services run 2 worker processes each and can be given more (gunicorn `--workers`) if needed.

## 6. Backup and restore

`infra/backup.sh` dumps every service database and archives uploaded media and private documents into `backups/<date-time>/` (permissions 700, with SHA-256 checksums), keeping 14 days. `infra/restore.sh <folder>` checks the checksums, asks for confirmation, restores everything and restarts the services.

**Restore test on the Docker stack:**

1. **Before:** application NCIT-2026-00001 with its uploaded transcript, an extra news article, a pending alumni registration, and 5 logged emails.
2. **Backed up**, then **deleted every container and data volume** (`docker compose down -v`) and started fresh. Only sample data remained: no application, no extra article.
3. **Restored**, after which everything was back:
   - the application, and the Admission Officer could open its transcript (served as a private PDF);
   - the article, the alumni registration and the email log;
   - search found the restored article, because the index rebuilt itself.

## 7. Automated tests

| Suite | Tests |
|---|---|
| ncit-common | 30 |
| auth | 39 |
| academics | 18 |
| content | 14 |
| events | 12 |
| ECA | 8 |
| admissions | 10 |
| careers | 4 |
| alumni | 5 |
| notifications | 12 |
| search | 6, run on both SQLite and PostgreSQL |
| audit | 4 |
| service template | 3 |
| **Total** | **165** |

CI now also starts a PostgreSQL service, so the search tests run on PostgreSQL full-text search there.

## Still to do before go-live

These need the college: real content, Google sign-in credentials, a mail server, the domain and server, and a final run of these tests on that server. See [GO-LIVE.md](GO-LIVE.md).
