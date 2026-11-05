# How the NCIT website was built, phase by phase

This is the build record: for each phase, **what was done**, **how it was done** (the decisions and techniques behind it) and **how it was checked**. The detailed guides for running and using each part are linked at the end of each phase.

| Phase | What | State | Guide |
|---|---|---|---|
| 0 | Foundations and design: monorepo, gateway, design system, first pages | Done | [CONTENT-GUIDE.md](CONTENT-GUIDE.md), [DESIGN.md](../DESIGN.md) |
| 1 | Sign-in and access control: Google sign-in for `@ncit.edu.np`, roles, Users & access, audit log | Done | [PHASE-1-AUTH.md](PHASE-1-AUTH.md) |
| 3 | Academics and HOD dashboard: department pages, each HOD edits their own (brought forward) | Done | [DEPARTMENTS.md](DEPARTMENTS.md) |
| 2 | Core content: banners and ads, leadership messages, news, notices, facilities | Done | [CONTENT.md](CONTENT.md) |
| 4 | Events, ECA and clubs: calendar, registrations, clubs, members, activities | Done | [EVENTS-AND-CLUBS.md](EVENTS-AND-CLUBS.md) |
| 5 | Admissions, careers and alumni: email-code sign-in, applications, review, status emails, alumni verification | Done | [ADMISSIONS-CAREERS-ALUMNI.md](ADMISSIONS-CAREERS-ALUMNI.md) |
| 6 | Search, hardening and launch: site search, SEO, About/Contact/Faculty/Privacy/Accessibility pages, security, accessibility, load and restore tests, Docker and HTTPS deployment, handover | Done; awaiting the college's sign-off | [LAUNCH-READINESS.md](LAUNCH-READINESS.md), [OPERATIONS.md](OPERATIONS.md), [ADMIN-GUIDE.md](ADMIN-GUIDE.md), [GO-LIVE.md](GO-LIVE.md) |

Phase 3 was done before Phase 2 because the college asked for department pages first.

---

## The pattern every phase follows

Every phase from 1 onwards was built the same way, so each one is predictable to review and to extend.

1. **One microservice per area, with its own database.** Each service is a small Flask app in `services/<name>-service/`, started from the `services/_template` skeleton. It has its own PostgreSQL database and login (created by `infra/postgres/init/01-databases.sh`) and never reads another service's tables. Schema changes are Alembic migrations, applied automatically when the container starts.
2. **One gateway.** nginx (`gateway/nginx.conf`) is the only public entry point. It serves the static site and sends `/api/v1/<service>/...` to the right service. Adding a service means one `upstream` line and its `location` blocks; nothing else changes. Public read endpoints are cached (in Redis by each service, and for 5 seconds at the gateway), and sign-in and sign-up endpoints are rate limited.
3. **Shared rules in one library.** `libs/ncit-common` holds the code every service must do the same way: checking the sign-in token, role checks (`@require_role`), CSRF protection, instant revocation, error responses, logging, audit events, field validation, safe uploads and, from Phase 4, the generic editing routes.
4. **Everything important is audited.** Services publish events ("role.granted", "news.published", "registrations.cancelled" …) to a Redis stream; the audit worker stores them; the Super Admin reads them in the Audit log.
5. **Content is plain text, escaped on display.** Editors can't inject HTML or scripts. Uploaded photos are decoded and re-encoded, which strips hidden data such as GPS location; PDFs are checked to be real PDFs.
6. **Starter content is marked.** Each new service seeds realistic sample content, marked "(sample)", into an empty database only, so restarting never overwrites real work.
7. **The site still works without the backend.** Every public page has preview data (`frontend/public/assets/data/*.json`) and the dashboard has a demo mode, so designs can be reviewed with `npm run serve` alone.
8. **Each phase has a gate**, an agreed condition that proves the phase works. It is checked twice: by automated tests named `test_gate_...`, and end to end on a real stack (PostgreSQL, Redis, nginx, the services and a headless browser), including phone-width layout checks.
9. **CI tests only what changed.** `.github/workflows/ci.yml` detects which folders changed and runs lint, tests and a Docker build for just those services.

```
Browser ──► nginx gateway ──► /                        static site (frontend/public)
                          ├─► /api/v1/auth/            auth-service      ─┐
                          ├─► /api/v1/audit/           audit-service      │ each with its own
                          ├─► /api/v1/academics/       academics-service  │ PostgreSQL database
                          ├─► /api/v1/content/         content-service    │
                          ├─► /api/v1/events/          event-service      │
                          ├─► /api/v1/eca/             eca-service        │
                          ├─► /api/v1/admissions/      admission-service  │
                          ├─► /api/v1/careers/         career-service     │
                          ├─► /api/v1/alumni/          alumni-service     │
                          ├─► /api/v1/notify/          notification-service │
                          ├─► /api/v1/search/, /sitemap.xml  search-service ─┘
                          └─► /media/                  public photos and PDFs (application documents are private)
             Redis: revoked sessions; the event stream (→ audit-worker, search-worker);
                    the mail queue (→ notification-worker → SMTP)
```

---

## Phase 0: Foundations and design

**Goal:** a codebase that can grow service by service, and a design the college approves before any feature work.

### What was done
- The monorepo layout: `frontend/`, `gateway/`, `libs/ncit-common/`, `services/_template/`, `infra/` (Docker Compose, PostgreSQL init) and CI.
- A design system in the "Classic university" direction the college chose: a photography-led banner, mega-menus, editorial news, events and notices, leadership messages and an Apply band.
- The first pages: home, a department page and the dashboard shell, all responsive and built mobile first.

### How it was done
- **Brand from the logo.** The colours were sampled from the NCIT emblem: royal blue for the institution, Om red reserved for Apply and urgent actions, and sky blue as an accent on dark backgrounds. They live in one place (the `@theme` block in `frontend/src/css/site.css`), so confirming the official colours is a one-file change. [DESIGN.md](../DESIGN.md) records the rules.
- **Typography:** Source Serif 4 for headings and Mukta for text (Mukta also covers Devanagari, ready for a Nepali version). Both are self-hosted rather than loaded from Google, for speed and privacy.
- **Tailwind CSS v4 without a JavaScript framework.** Pages are plain HTML in `frontend/src/pages`. Shared header, footer and head are partials in `frontend/src/partials`, included by `scripts/build-pages.mjs` into `frontend/public/`. Tailwind's command-line tool builds one CSS file. Icons are a single Lucide SVG sprite.
- **Photo slots:** every photo has a fixed name under `assets/img/photos/`, with a labelled placeholder until the real photo is added, so missing photos never break a layout.
- **Honest placeholders:** anything invented carries an amber **Sample** marker.
- **Accessibility from the start:** 44 px touch targets, visible focus states, a skip link, a carousel that can be paused and respects reduced motion, and contrast checked against WCAG AA.

### How it was checked
Desktop and phone screenshots of every page were reviewed against the design brief; no horizontal scrolling at 390 px wide.

---

## Phase 1: Sign-in and access control

**Goal:** only NCIT accounts can sign in; the Super Admin grants and removes every role from one screen; removing a role works immediately.

### What was done
- **auth-service:** Google sign-in limited to `@ncit.edu.np`, sessions, roles (with a department scope for HODs), invitations, CSV import, suspensions.
- **audit-service and audit-worker:** a permanent record of sign-ins, refused sign-ins and every access change.
- **Dashboard:** the real signed-in user, a menu that shows only what the user's roles allow, Users & access, Audit log. A login page with clear error messages.

### How it was done
- **Google OpenID Connect with three checks:** Google says the email is verified, the Workspace domain claim is `ncit.edu.np`, and the address ends in `@ncit.edu.np`. A personal Gmail, or a personal Google account registered with a college address, is refused and the refusal is logged.
- **Short-lived signed tokens:** auth-service signs a 15-minute access token (JWT, RS256). Other services verify it with the public key alone, with no call to auth-service per request. A refresh token, replaced on every use, keeps people signed in; reuse of an old one ends the whole session (theft detection).
- **Cookies, not local storage:** the tokens are HttpOnly cookies that page scripts can't read. Every change also sends a CSRF token (double-submit) so other websites can't act on a user's behalf.
- **Instant revocation:** removing a role, suspending a user or signing out writes a revocation entry to Redis, which every service checks on every request. Access is lost on the very next request, well inside the 15 minutes the gate allowed.
- **Safety rules:** at least one Super Admin must always remain; nobody can suspend themselves or remove their own Super Admin role.

### How it was checked
Gate: *outside emails are refused; a revoked role loses access within 15 minutes.* Tests cover lookalike domains, missing Workspace claims, revocation and audit storage. End to end: a Gmail address was refused and logged, and a revoked HOD's old token was rejected on its next use. Details: [PHASE-1-AUTH.md](PHASE-1-AUTH.md).

---

## Phase 3 (brought forward): Department pages and the HOD dashboard

**Goal:** every department has a page its HOD keeps up to date, and an HOD can edit only their own department.

### What was done
- **academics-service:** departments, programmes, semester-wise courses, faculty, labs and student testimonials, with photo uploads.
- One public template serves every department at `/departments/<name>`; the home page lists published departments.
- The **My department** editor for HODs, and **Departments** for the Super Admin (any department, publish or hide, add new ones).
- The same starter content for all eight departments, marked "(sample)", plus HOD sign-in setup (`HOD_ASSIGNMENTS`, and demo HOD accounts for local testing).

### How it was done
- **Scoped roles:** an HOD's role carries the department as its scope (`hod` for `dept:computer`). The route decorator compares it with the department in the URL, so even a hand-crafted request for another department is refused.
- **One template, data from the API:** `department.html` plus `department.js` render any department, so adding a department needs no new HTML.
- **Starter content that never overwrites:** seeding only fills departments that nobody has edited, and only their empty sections.

### How it was checked
Gate: *each HOD can edit only their own department.* Tests, plus end to end: the Computer HOD edited their page (overview, message, photo, courses, faculty, labs, testimonial) and was refused when trying to edit Civil. Details: [DEPARTMENTS.md](DEPARTMENTS.md).

The faculty directory, left over from this phase, was added in Phase 6.

---

## Phase 2: Core content

**Goal:** the home page and news pages are managed from the dashboard, with scheduling; the Super Admin schedules a banner and publishes a leadership message.

### What was done
- **content-service:** banners and ads (with "show from / until"), leadership messages (Executive Director, Director, Principal), news (scheduled publishing, one page per article), notices (categories, PDF attachments, pinning, automatic removal) and facilities.
- New public pages: `/news`, `/news/<article>`, `/notices`, `/leadership`. The home page banner, news, notices, leadership and facilities now come from the service.
- A **Website content** section in the dashboard for Super Admins and **Content Admins**.

### How it was done
- **Scheduling with no background jobs:** each item stores its time window, and the service decides what is live at the moment of each request (draft, scheduled, live, expired). Nothing needs to "run" at midnight.
- **Nepal time in, UTC stored:** editors type Nepal time; the service stores UTC and treats a time without a zone as Nepal time.
- **Shared field rules and uploads:** field validation (`ncit_common.fields`) and photo and PDF handling (`ncit_common.media`) moved into the shared library and are used by both academics-service and content-service. The original plan had a separate media service; doing it in the library gave the same safety with one less service to run.
- **The home page never goes blank:** it ships with the original content built in, and live content replaces it when the service answers.

### How it was checked
Gate: *Super Admin schedules a banner and publishes a message, end to end.* `test_gate_schedule_a_banner` and `test_gate_publish_a_leadership_message`, plus end to end: a live banner appeared on the home page while a scheduled one stayed hidden; the Principal's edited message appeared on `/leadership`; a pinned exam notice with a PDF topped the notices. Details: [CONTENT.md](CONTENT.md).

The About and Contact pages, left over from this phase, were added in Phase 6.

---

## Phase 4: Events, ECA and clubs

**Goal:** an events calendar with online registration and a clubs section with membership, run by an Event Admin and an ECA Admin who cannot edit each other's content.

### What was done
- **event-service:** events with categories, venue, organiser, cover photo and programme PDF; optional registration with a number of places, a closing time and an automatic waiting list; attendance; CSV export.
- **eca-service:** clubs, join requests with approval, committee positions, and club activities.
- Public pages: `/events` (Upcoming, Past, Month calendar, category filters), `/events/<name>` with a register button, `/clubs`, and `/clubs/<name>` with an "Ask to join" button. The home page's events and clubs come from the services.
- Dashboard: **Events** (with Registrations) for Event Admins; **Clubs** (with Members), **Join requests** and **Club activities** for ECA Admins; **My activity** for every signed-in user.
- Demo accounts for local testing: `event.admin@`, `eca.admin@` and `content.admin@ncit.edu.np`.

### How it was done
- **Two services, two roles:** events and clubs are separate services with separate databases, each guarded by its own role (`event_admin`, `eca_admin`). Keeping them apart is structural, not a setting that could be misconfigured.
- **The generic editor:** content-service had shown that every content type needs the same routes (list, add, edit, delete, reorder, upload). These became one function in the shared library, `ncit_common.editor.editor_blueprint`, which builds the routes from a short description of each collection. Events, clubs and activities were then mostly *descriptions*. content-service was moved onto the same function, with its tests unchanged, so all three services behave identically.
- **Correct waiting lists:** registering and cancelling lock the event row (`SELECT … FOR UPDATE`) while places are counted, so the last place can't be taken twice. Cancelling, an admin cancelling, or adding places moves the earliest waiting person up automatically.
- **Counts without extra queries:** places taken, people waiting, members and pending requests are loaded with each event or club as SQL subqueries.
- **Signed-in actions on public pages:** the event and club pages check the visitor's session in the background. Signed out, they show "Sign in to register"; signed in, one click registers. The same token and CSRF rules as the dashboard apply, and these endpoints are rate limited at the gateway.
- **Privacy by design:** the public site shows counts and committee names only; the lists of names are for admins.
- **Nepal time everywhere:** the calendar, event pages and dashboard show Nepal time whatever the visitor's computer is set to, so an editor abroad can't enter the wrong time.
- **Safe CSV:** values that Excel would treat as formulas (starting with `=`, `+`, `-` or `@`) are prefixed so they show as text.

### How it was checked
Gate: *Event Admin and ECA Admin cannot edit each other's content.* `test_gate_event_admin_and_eca_admin_are_separate` and `test_gate_eca_admin_and_event_admin_are_separate`, plus 14 more tests for registration, the waiting list, the calendar, membership and activities. End to end in a browser, as four different users:
- the Event Admin created an event, marked attendance and downloaded the CSV, and got 403 from the clubs APIs;
- a student registered for a workshop and asked to join the Robotics Club;
- the ECA Admin approved the request and made the student Treasurer, and got 403 when trying to create an event;
- the Super Admin saw every step in the Audit log.

No layout overflowed at phone width. Details: [EVENTS-AND-CLUBS.md](EVENTS-AND-CLUBS.md).

---

## Phase 5: Admissions, careers and alumni

**Goal:** people outside the college can apply for admission, apply for jobs and register as alumni; officers review what they send; everyone is emailed as things move.

### What was done
- **Sign-in by emailed code** (auth-service) for applicants and alumni, who have no college account.
- **notification-service:** a mail worker and the Super Admin's **Email log**. With no mail server configured, emails are recorded instead of sent.
- **admission-service:** intakes and programmes on offer; an online application with saving, document uploads and a reference number; the Admission Officer's review (under review, more documents, accepted, waiting list, not accepted), with internal notes and a CSV export.
- **career-service:** vacancies, applying with a CV, and the HR Officer's review (shortlist, interview, offer).
- **alumni-service:** alumni registration, the Alumni Coordinator's verification against college records, a public directory, and featured alumni on the home page.
- Public pages: `/admissions`, `/apply`, `/careers`, `/careers/<vacancy>`, `/alumni`, `/alumni/join`. The site's Apply, Admissions, Careers and Alumni links now go to them.
- Dashboard: Applications, Intakes, Programmes on offer, Vacancies, Job applications, Alumni verification, Email log; Users & access can list applicant and alumni accounts.

### How it was done
- **Outside accounts without passwords.** An emailed 6-digit code is safer than a password the applicant would reuse and forget. Only a keyed hash of the code is stored. A code works once, for 10 minutes and 5 tries; requests are limited per address and at the gateway. These accounts are marked *external* and get only an *Applicant* or *Alumni* role, which can't open anything in the dashboard. A Super Admin can never grant a dashboard role to an outside address.
- **A mail queue, not mail code everywhere.** Services drop a message (template name and data) on a separate Redis stream, `ncit:mail`. Only notification-service knows the wording of emails and how to reach the mail server. A mail outage never loses an application: the email is logged as *Failed* and can be sent again. The stream is separate from the audit events so sign-in codes never reach the audit log, and codes are removed from the Email log (subject and body) once sent.
- **Private documents.** `ncit_common.media` gained private storage. Transcripts, ID scans and CVs go to a volume the gateway never serves, and are handed out only by the owning service after checking who's asking, with no-store caching.
- **Explicit workflows.** Each kind of application has a small table of allowed moves (e.g. *documents requested* only back to *under review* or *not accepted*). Some moves need a message: asking for documents, an interview invitation, rejecting an alumni registration. Every step is kept in a history the applicant sees, without officers' names.
- **One review screen, four uses.** The dashboard's Applications, Job applications, Alumni verification and Email log are one module (`dashboard-review.js`) with a short description per screen, just as the content editors share one module.
- **Re-checking what matters.** A verified alumnus who changes their name, programme, year or registration number goes back to the coordinator; a new job title doesn't.

### How it was checked
Gate: *apply, review, status email and alumni verification work end to end.* The gate tests are `test_gate_apply_review_and_status_email` and `test_gate_alumni_verification`, plus 29 more tests across email codes, the mail worker, admissions, careers, alumni and private files. End to end, as six different users in a browser on the real stack:
- an applicant applied with an emailed code;
- the Admission Officer accepted the application with a message;
- the HR Officer invited a job applicant to interview;
- the Alumni Coordinator verified and featured an alumnus;
- the applicant saw the decision;
- the Super Admin saw every email in the Email log and every step in the Audit log.

Each officer got 403 from the others' areas. Running on PostgreSQL caught one bug the unit tests missed (an empty second choice), now fixed and tested. Details: [ADMISSIONS-CAREERS-ALUMNI.md](ADMISSIONS-CAREERS-ALUMNI.md).

---

## Phase 6: Search, hardening and launch

**Goal:** a site people can search and find on Google, that is secure, accessible and fast, that the college's IT staff can deploy, back up and run, and that its staff know how to use. Gate: *go-live sign-off by the college.*

### What was done
- **search-service:** one search box over every service's public content (departments, faculty, programmes, news, notices, events, clubs, vacancies and pages), with filters by kind and highlighted matches, at `/search` and from the search panel in the header.
- **SEO:**
  - an automatic `sitemap.xml` built from the same index, and `robots.txt`;
  - sharing (Open Graph) tags and canonical links on every page;
  - structured data marking the home page as a college.
- **The pages left over from earlier phases:**
  - About;
  - Contact, with a form that emails the college;
  - the Faculty directory;
  - Privacy notice and Accessibility statement.
  - Every placeholder link in the menus and footer now goes somewhere real.
- **Security:**
  - one set of security headers on every response;
  - dependencies upgraded to remove 98 published advisories;
  - an automated security test suite (`tools/security_check.py`);
  - a weekly dependency scan in CI.
- **Accessibility:** an axe audit of 65 page states and keyboard tests, with the problems found fixed.
- **Load test** (`tools/load_test.py`), **backup and restore scripts** (`infra/backup.sh`, `infra/restore.sh`), and an **HTTPS deployment** with Caddy (`infra/docker-compose.tls.yml`).
- **The full Docker Compose deployment tested for the first time,** which found four deployment bugs (all fixed).
- **Handover documents:** [OPERATIONS.md](OPERATIONS.md) for IT, [ADMIN-GUIDE.md](ADMIN-GUIDE.md) for staff training, [GO-LIVE.md](GO-LIVE.md) for the sign-off, and [LAUNCH-READINESS.md](LAUNCH-READINESS.md) for the test results.

### How it was done
- **Search indexes what the public can already see.** The search service reads each service's public endpoints, the same ones the website uses, so it can never expose a draft or private data. It never touches another service's database. It listens to the same event stream as the audit log, so a section is re-indexed seconds after an editor saves (measured: 2.1 seconds from publishing an article to finding it). There is also a full rebuild every 15 minutes, and a service that is briefly down keeps its old results instead of vanishing.
- **PostgreSQL full-text search, no extra search engine.** It uses a weighted index (title, then summary, then body), the "simple" language setting so Nepali names work, and prefix matching so "comp eng" finds Computer Engineering. The query and the index use the identical expression, so the index is actually used (verified with `EXPLAIN`). The tests run on both SQLite and PostgreSQL; the PostgreSQL run caught three issues the SQLite run couldn't.
- **SEO tags from the pages themselves.** The page builder reads each page's own title and description to write its sharing tags, so there's nothing to keep in sync by hand. Template pages (one article, event or club) get no canonical link, and sign-in pages are marked `noindex`.
- **Testing the deployment, not just the code.** The whole stack was built and run with Docker Compose, then tested with the same browser scripts and security suite. Problems that only exist in a real deployment surfaced:
  - missing database passwords;
  - databases created only on the very first start;
  - nginx caching service addresses that change when containers are recreated;
  - workers racing their own migrations.
- **A restore that has been proven.** The backup was tested by deleting every container and volume and restoring from it, then checking that the records, a private document and the search results all came back.
- **Accessibility checked by machine and by keyboard.** axe catches markup errors; scripted keyboard tests check what it can't: focus order, visible focus, Escape closing panels, 400% zoom and reduced motion.

### How it was checked
See [LAUNCH-READINESS.md](LAUNCH-READINESS.md):
- **Security:** 49/49 checks (32/32 over HTTPS); the dependency scan is clean. A later full review fixed 7 problems ([SECURITY-REVIEW.md](SECURITY-REVIEW.md)).
- **Accessibility:** 0 axe violations across 65 page states.
- **Load:** about 6,700 requests per second with 0 errors.
- **Restore:** a successful full restore from backup.
- **Tests:** 165 automated tests (after the Redis cache and notifications, [CACHING-AND-NOTIFICATIONS.md](CACHING-AND-NOTIFICATIONS.md)).

**The gate itself** is the college's signature on [GO-LIVE.md](GO-LIVE.md), after the content, accounts and server items there are done.

## Totals at the end of Phase 6

| | Count |
|---|---|
| Services | 11 (auth, audit with its worker, academics, content, events, ECA, admissions, careers, alumni, notifications with its worker, search with its worker) |
| Automated tests | 165 (ncit-common 30, template 3, auth 39, academics 18, content 14, events 12, ECA 8, admissions 10, careers 4, alumni 5, notifications 12, search 6, audit 4) |
| Public pages | home, about, contact, faculty directory, 8 department pages, news and articles, notices, leadership, events and event pages, calendar, clubs and club pages, admissions, apply, careers and vacancies, alumni directory, alumni registration, search, privacy, accessibility, login |
| Dashboard roles in use | Super Admin, Content Admin, Head of Department, Event Admin, ECA Admin, Admission Officer, HR Officer, Alumni Coordinator, and every signed-in user (My activity) |
| Outside accounts | Applicants and alumni, signing in with an emailed code |
| Tools for the college | `tools/security_check.py`, `tools/load_test.py`, `infra/backup.sh`, `infra/restore.sh`, `infra/setup_env.py` |

## Still untested (needs the college)

- **Real Google sign-in:** needs the college's Google OAuth client. Every check used the development login, which goes through the same session and role code.
- **Real email delivery:** no mail server was configured, so emails were recorded in the Email log rather than sent. The SMTP sending code is Python's standard library, but it hasn't been run against the college's mail server.
- **The production server itself:** the Docker deployment, HTTPS overlay, backups and restore were all tested on a build machine. They need one run on the real server, with its real domain (see [GO-LIVE.md](GO-LIVE.md) §C).
