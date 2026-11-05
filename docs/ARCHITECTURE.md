# How the NCIT website is implemented

The site is one nginx gateway in front of 11 independent Flask services. Each service owns its own PostgreSQL database and talks to the others only through a Redis event stream. The diagrams below are written in Mermaid, so GitHub draws them; the first is also saved as an image.

![NCIT system architecture](images/architecture.png)

## 1. The whole system

```mermaid
flowchart TB
    subgraph People
        V[Visitors and applicants<br/>website, apply, careers, alumni]
        S[College staff<br/>dashboard by role]
    end
    G([Google sign-in<br/>@ncit.edu.np only]):::ext
    S -. sign in .-> G

    C[Caddy<br/>HTTPS certificate, redirect]
    N[nginx gateway<br/>static pages · /api routing · 5 s cache<br/>rate limits · security headers]:::accent
    V --> C
    S --> C
    C --> N

    subgraph Services["11 Flask microservices (each with its own database)"]
        direction LR
        auth[auth<br/>sign-in, roles, codes]
        audit[audit<br/>audit log]
        academics[academics<br/>departments, faculty]
        content[content<br/>news, notices, banners]
        events[events<br/>calendar, registration]
        eca[eca<br/>clubs, members]
        admissions[admissions<br/>applications, review]
        careers[careers<br/>vacancies, CVs]
        alumni[alumni<br/>verification, directory]
        notification[notification<br/>Email log]
        search[search<br/>site search, sitemap]
    end
    N -->|/api/v1/&lt;service&gt;/| Services
    auth -. OIDC .-> G

    PG[(PostgreSQL<br/>one database per service)]
    R[(Redis<br/>ncit:events · ncit:mail · ncit:notify<br/>revoked sessions)]
    RC[(Redis cache<br/>public answers, LRU)]
    F[(File storage<br/>media: public · private: documents, CVs)]
    Services --> PG
    Services -->|publish events, queue mail and notifications| R
    Services <-->|public answers| RC
    Services --> F
    N -->|/media/| F

    AW[audit-worker]:::worker
    SW[search-worker]:::worker
    NW[notification-worker]:::worker
    R --> AW & SW & NW
    SW -->|reads public APIs| Services
    NW -->|SMTP| M([Mail server]):::ext

    classDef accent fill:#e6efff,stroke:#2d53c4,stroke-width:2px
    classDef worker fill:#f1f1ee,stroke:#888
    classDef ext stroke-dasharray:4 4
```

**Rules every part follows:**
- **One way in.** Only the gateway is reachable from outside (only Caddy, with the HTTPS setup). Services listen on an internal network.
- **Each service owns its data.** No service reads another's database. Shared behaviour (token checks, roles, CSRF, uploads, editor routes, the mail queue) lives in the `ncit-common` library that every service imports.
- **Events, not calls.** A service announces a change ("news.published", "applications.accepted") on the Redis stream. The audit worker stores it in the audit log; the search worker re-indexes the affected section.
- **Mail is queued.** Services put emails on a separate stream (`ncit:mail`), so one-time sign-in codes never reach the audit log. The notification worker sends them and keeps the Email log.
- **Notifications are queued too.** In-app notifications (the bell) go on `ncit:notify`. The same worker stores them, and notification-service shows each person only their own and their roles'.
- **Private files stay private.** Application documents and CVs are stored where the gateway can't serve them. Only the owning service hands them out, after checking who is asking.

## 2. What happens on a request

A signed-in Admission Officer accepting an application:

```mermaid
sequenceDiagram
    autonumber
    participant B as Browser (dashboard)
    participant N as nginx gateway
    participant A as admission-service
    participant DB as ncit_admissions DB
    participant R as Redis
    participant W as notification-worker
    participant AW as audit-worker

    B->>N: POST /api/v1/admissions/review/applications/{id}/status<br/>cookie ncit_access (JWT) + X-CSRF-Token
    N->>A: proxied (request id, rate limits, headers)
    A->>A: verify JWT with the public key, check revocation in Redis,<br/>check CSRF, check role admission_officer
    A->>DB: update status, add history entry
    A->>R: XADD ncit:mail (application_status email)
    A->>R: XADD ncit:events (applications.accepted)
    A-->>B: 200 updated application
    R-->>W: email consumed → rendered → SMTP → Email log
    R-->>AW: event consumed → stored in the audit log
```

Public pages (news, events, the home page data) are cached twice: for 5 seconds at the gateway, and in a separate Redis by each service, which drops its copies the moment anything changes. Most visitors never reach a database. Details: [CACHING-AND-NOTIFICATIONS.md](CACHING-AND-NOTIFICATIONS.md).

## 3. Sign-in

```mermaid
flowchart LR
    subgraph Staff["College accounts"]
        L[/login.html/] --> GG[Google OIDC] --> AU1[auth-service<br/>checks verified email,<br/>Workspace domain, @ncit.edu.np]
    end
    subgraph Outside["Applicants and alumni"]
        E[Enter email] --> CODE[6-digit code by email<br/>hashed, 10 min, 5 tries] --> AU2[auth-service<br/>external account,<br/>applicant or alumni role only]
    end
    AU1 --> T[Cookies: ncit_access JWT 15 min<br/>ncit_refresh rotating 7 days<br/>ncit_csrf]
    AU2 --> T
    T --> SVC[Every service verifies the JWT locally<br/>and checks the Redis revocation list]
```

Removing a role or suspending an account takes effect on the user's next request: auth-service writes the revocation to Redis, and every service checks it.

## 4. How the search stays current

```mermaid
flowchart LR
    ED[Editor saves in the dashboard] --> SVC[content / events / eca /<br/>academics / careers / admissions]
    SVC -->|event| R[(Redis ncit:events)]
    R --> SW[search-worker]
    SW -->|reads the same public APIs the website uses| SVC
    SW --> IDX[(ncit_search<br/>PostgreSQL full-text index)]
    Q[Visitor searches /search] --> N[gateway, 5 s cache] --> SS[search-service] --> RC2[(Redis cache)] --> IDX
    SS --> SM[/sitemap.xml/]
```

The search index only ever contains what the public can already see, because it is built from the public APIs. A full rebuild also runs every 15 minutes, as a safety net.

## 5. Deployment

```mermaid
flowchart TB
    subgraph Server["One Linux server, Docker Compose"]
        CADDY[caddy :80 :443] --> GW[gateway]
        GW --> SVCS[11 services]
        DBS[db-setup<br/>runs once per start:<br/>creates missing databases] --> PG[(postgres)]
        SVCS --> PG
        SVCS --> RD[(redis)]
        WK[3 workers] --> RD
        V1[(volume: pgdata)] --- PG
        V2[(volume: media)] --- SVCS
        V3[(volume: private)] --- SVCS
    end
    BK[infra/backup.sh<br/>nightly] -->|dumps + archives| OFF[(Off-server copy)]
    CI[GitHub Actions<br/>tests per changed service,<br/>weekly dependency scan] -.-> Server
```

| File | Role |
|---|---|
| `infra/docker-compose.yml` | Every service, worker, database, Redis and the gateway |
| `infra/docker-compose.tls.yml` | Adds Caddy for HTTPS; closes the gateway's own port |
| `infra/postgres/init/01-databases.sh` | Creates one database and login per service; safe to re-run |
| `gateway/nginx.conf` | Routing, caching, rate limits, security headers |
| `infra/backup.sh`, `infra/restore.sh` | Backups and restore |
| `.github/workflows/ci.yml` | Tests only what changed; weekly vulnerability scan |

## 6. Repository layout

```
frontend/            Public site and dashboard: HTML pages + Tailwind + plain JavaScript modules
  src/pages/         Page sources (built into public/ by scripts/build-pages.mjs)
  public/assets/js/  One module per page area (campus-pages.js, admissions-pages.js, dashboard-*.js …)
gateway/nginx.conf   The single entry point
libs/ncit-common/    Shared Python: auth, roles, CSRF, revocation, events, mail, fields, media, editor routes
services/<name>-service/
  app/               Flask app: models, routes (public / me / editor), rules
  migrations/        Alembic, run on start
  tests/             pytest
infra/               Docker Compose, database setup, backup and restore
tools/               security_check.py, load_test.py
docs/                Guides, reports and this file
```

## 7. Services at a glance

| Service | Database | Public routes | Signed-in routes | Editors |
|---|---|---|---|---|
| auth | ncit_auth | `/config` | `/me`, `/code/*`, `/google/*` | Super Admin (Users & access) |
| audit | ncit_audit | none | none | Super Admin (Audit log) |
| academics | ncit_academics | departments, faculty | none | HOD (own department), Super Admin |
| content | ncit_content | home, news, notices, leadership, contact form | none | Content Admin |
| events | ncit_events | events, calendar | register, cancel, my registrations | Event Admin |
| eca | ncit_eca | clubs, activities | join, leave, my clubs | ECA Admin |
| admissions | ncit_admissions | open intakes | my applications, documents | Admission Officer |
| careers | ncit_careers | vacancies | apply with CV, my applications | HR Officer |
| alumni | ncit_alumni | directory, featured | my profile | Alumni Coordinator |
| notification | ncit_notify | none | none | Super Admin (Email log) |
| search | ncit_search | search, sitemap.xml | none | Super Admin (status, rebuild) |
