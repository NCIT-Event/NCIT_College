# Caching, notifications, and the sign-in and access review

Added on 2026-11-04. This covers three things:

- a **Redis cache** that makes the public site faster;
- **in-app notifications** (the bell) for staff, students, applicants and alumni;
- a **review of sign-in and access control**, with the fixes that came out of it.

## 1. Redis page cache

### What it does

Every public read goes through the same path: news, notices, events, the calendar, clubs, department pages, the faculty directory, intakes, vacancies, the alumni directory, search and the sitemap. The service now first looks in Redis for an answer to that exact address. If it finds one, it answers in about a millisecond, without touching its database. If not, it builds the answer as before and keeps a copy.

```
visitor → nginx (keeps answers 5 s) → service → Redis cache ──hit──→ answer (≈1 ms)
                                          └──miss──→ PostgreSQL → answer, copy kept in Redis
```

### Why it is safe

| Concern | How it is handled |
|---|---|
| **Showing one person's data to another** | Only the anonymous `public` routes are cached. Signed-in routes (`/me/…`, every editor, the bell) never are, and neither is any answer that sets a cookie. `security_check.py` checks this on every run. |
| **Out-of-date pages after an edit** | Every successful change through a service starts a new cache version for that service, so all its cached answers are dropped at once. Changes include an editor saving, a student registering (which changes "places left") and a club approval. The search worker does the same after each re-index. The gateway keeps answers for at most 5 seconds (it was 30), so **an edit is on the website within about 5 seconds**. |
| **Things that change by the clock** | A banner's "show until" time, or registration closing, can be up to 60 seconds late (`PUBLIC_CACHE_TTL`). |
| **Filling memory with junk addresses** | Addresses with over-long query strings aren't cached. The cache runs in **its own Redis** (`cache` container): 128 MB, oldest entries evicted first, nothing written to disk. A full cache can never push out sessions, revocations or the event and mail queues, which live in the main `redis`. |
| **Redis down or slow** | The cache gives up after half a second and the service answers from the database as before. A warning is logged, at most once a minute. |

### Measured

All measurements were taken on the same machine, back to back.

| | Before | After |
|---|---|---|
| Public API answer, average of 11 endpoints (service measured directly) | 5.6 ms | **1.2 ms** |
| Department page, 20 at once (service measured directly) | 223 requests/s | **2,583 requests/s** |
| Whole site through the gateway, 100 simultaneous visitors | 3,007 requests/s, slowest 1% at 762 ms | **4,057 requests/s, slowest 1% at 103 ms**, 0 errors |

The whole-site figures are lower than the 6,700 requests/s in [LAUNCH-READINESS.md](LAUNCH-READINESS.md) because this machine was busier on this day. The before/after pair was measured under the same conditions.

### Settings

| Setting | Default | What it does |
|---|---|---|
| `CACHE_REDIS_URL` | `redis://cache:6379/0` in Docker | Where the cache lives. Empty means the main Redis. |
| `PUBLIC_CACHE_TTL` | 60 | The longest a cached answer is kept, in seconds. |
| `PUBLIC_CACHE` | on | `off` turns the cache off, e.g. to compare speeds. |

Every cached answer carries a header, `X-App-Cache: HIT` or `MISS`, which is useful when checking.

The code is in `libs/ncit-common/ncit_common/cache.py`. Each service turns it on with one line, `init_shared(app, client, SERVICE_NAME)`.

## 2. Notifications (the bell)

### What people see

A bell sits in the website header and in the dashboard top bar for anyone signed in. A red badge shows how many notifications are unread. Clicking the bell opens the latest notifications. Clicking one opens the page it is about and marks it read. **Mark all as read** clears the badge, and **Show older** pages back. Visitors who aren't signed in never see the bell, and their browser never even downloads it.

The badge is checked every minute while the tab is open, and again as soon as you come back to the tab. A new notification usually shows within a minute; the server stores it in a few hundredths of a second.

### What sends a notification

| When | Who is told | Opens |
|---|---|---|
| An application is sent (or sent again) | every **Admission Officer** | that application in the dashboard |
| An application moves to a new step (under review, more documents, accepted, waiting list, not accepted) | the **applicant** (same as the email; a quiet correction tells nobody) | `/apply` |
| A job application arrives | every **HR Officer** | Job applications |
| A job application moves on (shortlisted, interview, offer, not taken forward) | the **job applicant** | the vacancy |
| An alumni registration is sent | every **Alumni Coordinator** | Alumni verification |
| An alumni registration is verified, or can't be verified | the **graduate** | `/alumni/join` |
| A student asks to join a club | every **ECA Admin** | Join requests |
| A join request is approved or declined, someone is removed, or given a committee position | the **student** | the club page |
| Someone moves up from an event waiting list (a cancellation, more places, or the organiser admits them) | the **student** | the event |
| The organisers cancel someone's registration | the **student** | the event |
| A role is given or removed in Users & access | the **person** | the dashboard |

Emails are unchanged: notifications come in addition to them, never instead.

### Who can see what

- A notification sent to **a person** is seen by that person only.
- A notification sent to **a role** is seen by everyone who holds that role *at the moment they look*, so someone whose role is removed stops seeing that role's notifications at once. A role notification can be limited to a scope (one department's HOD).
- **Super Admins don't receive every role's notifications**, which would bury the ones meant for them.
- Reading is per person: one Admission Officer reading a notification doesn't mark it read for the others.
- Nobody can read or mark anyone else's notifications. Asking for another person's notification by its ID does nothing.
- Links can only point to pages on this site.
- Role notifications are kept for 30 days and personal ones for 180 days; older ones are deleted automatically.

### How it works

```
service ──notify()──→ Redis stream ncit:notify ──→ notification worker ──→ ncit_notify database
                                                                          ↑
browser bell ──GET /api/v1/notify/me/notifications (every minute)──→ notification-service
```

- The worker that already sends the emails (`ncit:mail`) reads both queues in one call, so neither waits for the other.
- A notification is acknowledged only after it is saved. If the worker stops, nothing is lost, and each one is stored once even if it is delivered twice.
- `notify()` never raises an error. If Redis is down, the change that caused the notification still succeeds.
- API (signed in; changes need the CSRF token):
  - `GET /api/v1/notify/me/notifications?page=&per_page=`
  - `GET /api/v1/notify/me/notifications/unread`
  - `POST /api/v1/notify/me/notifications/read` with `{"ids": [...]}` or `{"all": true}`
- Code:
  - `libs/ncit-common/ncit_common/notify.py`
  - `services/notification-service/app/inbox.py`, `routes/me.py`, `worker.py`
  - `frontend/public/assets/js/notifications.js`

## 3. Sign-in and access control: what was checked, and the fixes

The full security review of 2026-11-04 is in [SECURITY-REVIEW.md](SECURITY-REVIEW.md). For this work, sign-in and access control were checked again, including everything added here.

**Checked and sound:**
- Suspended accounts can't renew a session.
- Signing out revokes the access token at once.
- Refresh-token reuse ends the whole session family.
- Staff roles can only be given to `@ncit.edu.np` addresses.
- There is always one Super Admin left.
- Every one of the 8 roles is refused by the others' areas.
- The new notification API needs a sign-in, a CSRF token for changes, and shows each person only their own.

**Fixed:**

| Problem | Fix |
|---|---|
| **A role with an expiry date kept working for up to 15 minutes after it expired**, because the 15-minute sign-in token still listed it. | The token now ends when the earliest of its roles expires. The next renewal leaves that role out. Test: `test_access_token_ends_when_a_role_expires`. |
| **Everyone on campus could be locked out of sign-in.** Rate limits count requests per internet address, and a campus usually shares one. A busy morning (everyone signing in, or registering for an event) would hit the limit of 20 sign-ins per minute, and people would see "Too many requests". | Trusted campus networks can be listed in `gateway/campus-networks.conf` and are exempt. Brute force is still blocked by the services themselves: 5 tries per code and 3 codes per email per 15 minutes, and Google protects its own sign-in. **College IT must fill in the campus address** ([GO-LIVE.md](GO-LIVE.md)). |

## 4. Tests

- **19 new automated tests, 165 in total, all passing:**
  - the cache (8 in `ncit-common`, 1 inside a real service);
  - notifications (5 in notification-service, plus one for each service that sends them);
  - the role-expiry fix.
- **`tools/security_check.py --dev`: 52 of 52.** New checks:
  - notifications are private and never cached;
  - marking read needs the CSRF token;
  - signed-in answers never come from the page cache.
- **End to end through the gateway and worker:** every flow above was exercised and each person saw only their own notifications.
- **Browser:**
  - the bell on the home page, the dashboard and a phone, with 0 accessibility violations;
  - Escape closes it and returns focus to the bell;
  - no sideways scrolling on a phone;
  - no bell, and no download of it, for visitors who aren't signed in.
