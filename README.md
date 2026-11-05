# NCIT Website

Official website and content platform for Nepal College of Information Technology. Flask microservices behind an Nginx gateway, PostgreSQL per service, and a static HTML + Tailwind CSS + vanilla JS front end.

See `PRODUCT.md` (product facts), `DESIGN.md` (design system) and the design plan for the phased roadmap.

**Changing the logo, photos or page text? Start with [`docs/CONTENT-GUIDE.md`](docs/CONTENT-GUIDE.md).**
**Setting up Google sign-in and the dashboard? See [`docs/PHASE-1-AUTH.md`](docs/PHASE-1-AUTH.md).**
**Editing department pages? See [`docs/DEPARTMENTS.md`](docs/DEPARTMENTS.md).**
**Editing banners, news, notices, leadership messages or facilities? See [`docs/CONTENT.md`](docs/CONTENT.md).**
**Running events, registrations or clubs? See [`docs/EVENTS-AND-CLUBS.md`](docs/EVENTS-AND-CLUBS.md).**
**Admissions, careers, alumni and email? See [`docs/ADMISSIONS-CAREERS-ALUMNI.md`](docs/ADMISSIONS-CAREERS-ALUMNI.md).**
**What was built in each phase, and how: [`docs/PHASES.md`](docs/PHASES.md) · every task done: [`docs/WORK-LOG.md`](docs/WORK-LOG.md) · how the system fits together (diagrams): [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).**

**Launching and running it:** [`docs/OPERATIONS.md`](docs/OPERATIONS.md) (server, deployment, backups, monitoring) · [`docs/GO-LIVE.md`](docs/GO-LIVE.md) (checklist and sign-off) · [`docs/ADMIN-GUIDE.md`](docs/ADMIN-GUIDE.md) (staff training) · [`docs/LAUNCH-READINESS.md`](docs/LAUNCH-READINESS.md) (security, accessibility, load and restore test results) · [`docs/SECURITY-REVIEW.md`](docs/SECURITY-REVIEW.md) (full security review and fixes) · [`docs/CACHING-AND-NOTIFICATIONS.md`](docs/CACHING-AND-NOTIFICATIONS.md) (Redis page cache, the notification bell, sign-in and access review).

## Status

| Phase | What | State |
|---|---|---|
| 0 | Monorepo, gateway, design system, home / department / dashboard pages | Done |
| 1 | Google sign-in for @ncit.edu.np, roles, Users & access, audit log | Done |
| 3 | Department pages managed from the dashboard (academics-service) | Done (brought forward) |
| 2 | Content service: banners and ads, leadership messages, news, notices, facilities | Done |
| 4 | Events (calendar, registration, waiting lists), ECA and clubs (join requests, members, activities) | Done |
| 5 | Admissions, careers and alumni: email-code sign-in, online applications and review, status emails, alumni verification | Done |
| 6 | Search, SEO, About/Contact/Faculty pages, security, accessibility, load and restore tests, Docker + HTTPS deployment, handover | Done: awaiting the college's go-live sign-off |

## Layout

```
gateway/              Nginx API gateway (routes /api/v1/<service>/, security headers, caching)
frontend/             Public site and dashboards
  src/pages/          Page sources (assembled into public/)
  src/partials/       Shared header, footer, head
  src/css/site.css    Tailwind v4 entry: brand tokens and components
  public/             Built site served by Nginx (assets/js, assets/fonts, assets/img)
libs/ncit-common/     Shared Python: JWT verification, @require_role, CSRF, revocation, events, logging,
                      field validation, safe uploads, generic editor routes
services/auth-service/   Google sign-in, sessions, roles, Users & access API
services/audit-service/  Audit log API + worker that records events from Redis
services/academics-service/  Departments, programmes, courses, faculty, labs, testimonials, photo uploads
services/content-service/    Banners and ads, leadership messages, news, notices (PDFs), facilities
services/event-service/      Events calendar, registrations, waiting lists, attendance
services/eca-service/        Clubs, join requests and members, club activities
services/admission-service/  Intakes, programmes on offer, online applications and their review
services/career-service/     Vacancies and job applications (CVs)
services/alumni-service/     Alumni registration, verification and the directory
services/notification-service/  Sends the website's emails (worker) and keeps the Email log
services/search-service/     Site search over every service's public content, and sitemap.xml
services/_template/   Copy this to start a new Flask microservice
infra/                docker-compose (+ docker-compose.tls.yml for HTTPS), database setup, backup.sh, restore.sh
tools/                security_check.py, load_test.py (run against any copy of the site)
.github/workflows/    CI that tests and builds only what changed
```

## Run the front end

```bash
cd frontend
npm install
npm run build        # assemble pages + compile CSS
npm run serve        # http://localhost:5173 (also serves /departments/<slug>)
npm run dev          # rebuild CSS on change
```

Pages include `/` (home), `/about`, `/contact`, `/faculty`, `/departments/computer`, `/news`, `/notices`, `/events`, `/clubs`, `/admissions`, `/apply`, `/careers`, `/alumni`, `/search`, `/login.html` and `/dashboard/`. Without a backend running, pages use labelled preview data and the dashboard runs in demo mode.

## Run the full stack

```bash
pip install cryptography && python3 infra/setup_env.py   # once: creates .env with fresh keys
# edit .env: Google client ID/secret and SUPER_ADMIN_EMAILS (see docs/PHASE-1-AUTH.md)
docker compose -f infra/docker-compose.yml --env-file .env up --build
# site: http://localhost:8080   sign in: http://localhost:8080/login.html
```

On a server with a domain, add the HTTPS overlay (Caddy gets the certificate automatically):

```bash
docker compose -f infra/docker-compose.yml -f infra/docker-compose.tls.yml --env-file .env up -d --build
```

Back up with `infra/backup.sh` and restore with `infra/restore.sh <folder>`. Full instructions: [`docs/OPERATIONS.md`](docs/OPERATIONS.md).

No Google credentials yet? Set `DEV_LOGIN=true` (local only) to sign in as any @ncit.edu.np address. Demo Heads of Department (`hod.computer@ncit.edu.np`, `hod.civil@ncit.edu.np` …) and demo admins (`content.admin@`, `event.admin@`, `eca.admin@`, `admissions.officer@`, `hr.officer@`, `alumni.coordinator@ncit.edu.np`) are listed on the login page; any other college address signs in as a student.

## Tests

```bash
pip install -e "libs/ncit-common[dev]"
pip install -r services/auth-service/requirements.txt -r services/audit-service/requirements.txt -r services/academics-service/requirements.txt -r services/content-service/requirements.txt -r services/event-service/requirements.txt -r services/eca-service/requirements.txt -r services/admission-service/requirements.txt -r services/career-service/requirements.txt -r services/alumni-service/requirements.txt -r services/notification-service/requirements.txt -r services/search-service/requirements.txt
(cd libs/ncit-common && pytest -q)
(cd services/auth-service && pytest -q)
(cd services/academics-service && pytest -q)
(cd services/content-service && pytest -q)
(cd services/event-service && pytest -q)
(cd services/eca-service && pytest -q)
(cd services/admission-service && pytest -q)
(cd services/career-service && pytest -q)
(cd services/alumni-service && pytest -q)
(cd services/notification-service && pytest -q)   # TEST_REDIS_URL=… to include the worker test
(cd services/search-service && pytest -q)         # TEST_DATABASE_URL=postgresql+psycopg://… to test PostgreSQL full-text search
(cd services/audit-service && pytest -q)       # TEST_REDIS_URL=redis://localhost:6379/15 to include the worker test
```

## Adding a service

1. Copy `services/_template` to `services/<name>-service` and set `SERVICE_NAME`.
2. Add its database and user in `infra/postgres/init/01-databases.sh` and a password in `.env.example` / `infra/setup_env.py`.
3. Add the service to `infra/docker-compose.yml` and one `upstream` + `location /api/v1/<name>/` to `gateway/nginx.conf`.
4. Add a CI job filtered on its folder.

No existing service changes.

## Content still needed from the college

Logo file, confirmed brand colours, real photos (see `frontend/public/assets/img/photos/README.md`), programme and department list, leadership names and messages, contact details. Everything invented is marked **Sample** on the page.
