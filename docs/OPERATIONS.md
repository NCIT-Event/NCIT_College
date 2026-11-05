# Running the NCIT website

For the college's IT staff: setting up the server, deploying, updating, backups, monitoring and fixing common problems. Everything runs with Docker Compose on one Linux server.

## 1. The server

| | Minimum | Comfortable |
|---|---|---|
| CPU / memory | 2 cores, 4 GB | 4 cores, 8 GB |
| Disk | 40 GB SSD | 100 GB SSD (photos, PDFs and applicants' documents grow over time) |
| System | Ubuntu 24.04 LTS (or any Linux with Docker 25+ and Docker Compose v2.24+) | |
| Network | Ports 80 and 443 open to the internet; a DNS **A** record for the domain pointing at the server | |

What runs: 11 Python services, 3 background workers, PostgreSQL 16, Redis 7, the nginx gateway, and Caddy for HTTPS. One PostgreSQL instance holds one database per service.

## 2. First deployment

```bash
# on the server, as a user in the docker group
git clone https://github.com/Manil-Vaidhya/NCIT.git ncit && cd ncit
pip install cryptography && python3 infra/setup_env.py        # writes .env with fresh secrets
nano .env
```

In `.env`, set:

| Setting | What to put |
|---|---|
| `SITE_DOMAIN`, `SITE_URL` | e.g. `ncit.edu.np` and `https://ncit.edu.np` |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `OAUTH_REDIRECT_URI` | The Google OAuth client ([PHASE-1-AUTH.md](PHASE-1-AUTH.md)); the redirect URI becomes `https://ncit.edu.np/api/v1/auth/google/callback` |
| `SUPER_ADMIN_EMAILS` | The first Super Admin's `@ncit.edu.np` address |
| `HOD_ASSIGNMENTS` | Optional: department=email pairs |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_FROM` | The mail server ([ADMISSIONS-CAREERS-ALUMNI.md](ADMISSIONS-CAREERS-ALUMNI.md#emails-super-admin--email-log)) |
| `CONTACT_EMAIL` | Where Contact-page messages go |
| `COOKIE_SECURE=true`, `DEV_LOGIN=false`, `MAIL_KEEP_SENSITIVE=false` | **Must** be these values in production |

Build the front end once (or use the committed `frontend/public/`), then start:

```bash
(cd frontend && npm ci && npm run build)
docker compose -f infra/docker-compose.yml -f infra/docker-compose.tls.yml --env-file .env up -d --build
```

The first start takes a few minutes. It creates the databases (the `db-setup` container), runs every migration, seeds the starter content, builds the search index, and obtains the HTTPS certificate.

Check:

```bash
docker compose -f infra/docker-compose.yml -f infra/docker-compose.tls.yml --env-file .env ps   # all "healthy" (workers just "Up"; db-setup "Exited (0)")
curl -I https://ncit.edu.np/                                       # 200, with strict-transport-security
python3 tools/security_check.py https://ncit.edu.np                # all PASS
```

Tip: put the long command in a shell alias so you don't retype it:

```bash
echo 'alias ncit="docker compose -f infra/docker-compose.yml -f infra/docker-compose.tls.yml --env-file .env"' >> ~/.bashrc
```

Then use `ncit ps`, `ncit logs -f content-service` and `ncit up -d`.

**Without the HTTPS overlay** (for a staging server behind another proxy, or a laptop), leave out `-f infra/docker-compose.tls.yml`. The gateway then listens on `HTTP_PORT` (default 8080). If another proxy handles HTTPS, it must send `X-Forwarded-Proto: https`.

## 3. Updating

```bash
cd ncit
infra/backup.sh                                                    # 1. back up first
git pull                                                           # 2. new code
(cd frontend && npm ci && npm run build)                           # 3. if the front end changed
ncit up -d --build                                                 # 4. rebuild and restart what changed
ncit ps                                                            # 5. everything healthy again
```

Migrations run automatically when each service starts. A new service added in an update gets its database automatically (via `db-setup`). Visitors see at most a few seconds of errors while a service restarts.

**Rolling back:** `git checkout <previous tag>`, then `ncit up -d --build`. If a migration changed data, restore the backup taken in step 1 (see §4).

## 4. Backups

```bash
infra/backup.sh                                    # → backups/2026-11-03_0200/
BACKUP_DIR=/mnt/nas/ncit KEEP_DAYS=30 infra/backup.sh
```

It saves:

- every service database (PostgreSQL dumps);
- uploaded photos and PDFs;
- private application documents and CVs;
- checksums for all of the above.

It doesn't save Redis (sign-in sessions and queues) or the search index; both rebuild themselves.

**Every night**, with an off-server copy (`crontab -e`):

```cron
# 02:15 every night: back up, then copy off the server
15 2 * * * cd /home/ncit/ncit && COMPOSE="docker compose -f infra/docker-compose.yml -f infra/docker-compose.tls.yml --env-file .env" infra/backup.sh >> /var/log/ncit-backup.log 2>&1 && rsync -a backups/ backup-host:/srv/ncit-backups/
```

The backups contain applicants' personal data and documents. Keep the folder and the off-server copy private, and encrypted if they leave the college.

**Restoring** (replaces the current data):

```bash
infra/restore.sh backups/2026-11-03_0200        # checks checksums, asks you to type RESTORE
```

**Test a restore every few months** on a spare machine: bring up the stack, restore last night's backup, and sign in to check. A backup that has never been restored isn't proven.

Also keep `.env` somewhere safe (a password manager). Without it, the backups restore but nobody can sign in: the signing key and the database passwords are in it.

## 5. Monitoring

| What | How |
|---|---|
| Is everything up? | `ncit ps`: services "healthy", workers "Up". Each service has `GET /health` |
| Public check from outside | Point an uptime monitor (e.g. UptimeRobot, free) at `https://ncit.edu.np/api/health` |
| Logs | `ncit logs -f <service>`. Logs are JSON lines with a `request_id`, so one request can be followed from the gateway into the service |
| Emails failing | Dashboard → **Email log** (Super Admin): look for *Failed* entries |
| Search out of date | It updates seconds after each edit and fully every 15 minutes. `GET /api/v1/search/status` (Super Admin) shows when each part was last indexed; `POST /api/v1/search/reindex` rebuilds now |
| Who changed what | Dashboard → **Audit log** |
| Disk space | `df -h` and `docker system df`. Photos, documents and backups grow; old Docker images can be removed with `docker image prune` |

## 6. Common tasks

| Task | How |
|---|---|
| Add another Super Admin | Dashboard → Users & access → Grant a role, or `ncit exec auth-service flask --app wsgi grant-super-admin someone@ncit.edu.np` |
| Someone leaves the college | Dashboard → Users & access → remove their roles or **Suspend**. Takes effect on their next click |
| Suspend an applicant or alumni account | Users & access → filter *Applicants & alumni* → Suspend |
| Change who receives Contact messages | `CONTACT_EMAIL` in `.env`, then `ncit up -d content-service` |
| Rebuild the search index now | `ncit restart search-worker` (it rebuilds everything when it starts) |
| Replace the logo or a page photo | See [CONTENT-GUIDE.md](CONTENT-GUIDE.md); after changing `frontend/`, run `npm run build` |
| Sign everyone out (e.g. after a suspected leak) | Generate new keys with `python3 infra/setup_env.py --output new.env`, copy `SECRET_KEY`, `JWT_PRIVATE_KEY` and `JWT_PUBLIC_KEY` into `.env`, then `ncit up -d` |
| Run the security checks again | `python3 tools/security_check.py https://ncit.edu.np` (read-only, safe on production) |
| Load test | `python3 tools/load_test.py https://staging-address` (heavy: use staging, or production at night) |

## 7. Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| A service keeps restarting | `ncit logs --tail 50 <service>`. "password authentication failed" means `.env` passwords changed: run `ncit up -d db-setup` (it resets them), then `ncit up -d` |
| 502 Bad Gateway | A service is down or restarting: `ncit ps`, then read its logs |
| Google sign-in says "not configured" | `GOOGLE_CLIENT_ID` or `GOOGLE_CLIENT_SECRET` missing, or `OAUTH_REDIRECT_URI` doesn't match the Google Cloud console exactly |
| Applicants don't get codes | Email log shows *Recorded, not sent*: `SMTP_HOST` is empty. *Failed*: wrong SMTP settings or a blocked port. Codes landing in spam: set up SPF and DKIM for the sending domain |
| A change in the dashboard isn't on the site | The gateway keeps public answers for 5 seconds; wait and reload. Clock-based changes (a banner's end time) can take up to `PUBLIC_CACHE_TTL` (60 s). `curl -sI <api address> \| grep X-App-Cache` shows HIT or MISS |
| On campus, people see "Too many requests" when signing in | The campus's shared internet address hit the per-address limit. Add it to `gateway/campus-networks.conf`, then `ncit restart gateway` |
| The bell never shows anything | `ncit logs notification-worker`: it should say "listening on ncit:mail and ncit:notify". Check the `cache` and `redis` containers are up (`ncit ps`) |
| HTTPS certificate not issued | DNS must point at the server and ports 80 and 443 must be open; `ncit logs caddy` shows why |
| Disk full | `docker system prune` (old images), move old backups off the server, check `docker system df` |
| `up` fails with "Pool overlaps with other one on this network" | The site's Docker network `172.30.0.0/24` clashes with one already on the server. Pick a free range and change it in **three** places: the subnet in `infra/docker-compose.yml`, Caddy's `ipv4_address` in `infra/docker-compose.tls.yml`, and both `172.30.0.250` lines in `gateway/nginx.conf`. The gateway trusts the visitor address only from Caddy's address, so they must match |
| The Audit log shows the same address for everyone | Caddy's address and `set_real_ip_from` in `gateway/nginx.conf` don't match (see the row above) |

## 8. Security routine

- **Never** run production with `DEV_LOGIN=true`, `COOKIE_SECURE=false` or `MAIL_KEEP_SENSITIVE=true`.
- Keep the server patched (`unattended-upgrades` on Ubuntu), and open only ports 22 (SSH, keys only), 80 and 443.
- CI checks dependencies for known vulnerabilities on every change and weekly. When it fails, update the named package in `services/*/requirements.txt`, run the tests and deploy.
- Review Users & access each semester: remove roles from people who have changed jobs.
- Run `tools/security_check.py` after each update.
