# Admissions, careers and alumni (Phase 5)

Phase 5 lets people **outside** the college use the website: prospective students apply for admission, job seekers apply for vacancies, and graduates register as alumni. College staff review what they send from the dashboard, and the website emails them at every step.

| What | On the website | Run by | Dashboard | Service |
|---|---|---|---|---|
| **Admissions** | `/admissions` (programmes, seats, dates), `/apply` (apply and track) | **Admission Officer** | Applications · Intakes · Programmes on offer | admission-service |
| **Careers** | `/careers`, `/careers/<vacancy>` (apply with a CV) | **HR Officer** | Vacancies · Job applications | career-service |
| **Alumni** | `/alumni` (directory), `/alumni/join` (register), featured alumni on the home page | **Alumni Coordinator** | Alumni verification | alumni-service |
| **Emails** | | **Super Admin** | Email log | notification-service |

Each officer sees only their own area: an Admission Officer can't open job applications or alumni records, and the other roles likewise. This is checked by tests and in the browser.

## Signing in without a college account

Applicants and alumni usually don't have an `@ncit.edu.np` account, so they sign in with a **one-time code**:

1. They enter their email address, and the website emails them a 6-digit code.
2. They type the code and are signed in. They come back later with the same email address.

The rules:

- A code works **once**, for **10 minutes**, and stops working after **5 wrong tries**.
- At most 3 codes per address every 15 minutes. The gateway also limits how fast codes can be requested.
- Only a scrambled (hashed) form of the code is stored. The code never appears in the audit log, and it is removed from the Email log once sent.
- `@ncit.edu.np` addresses are sent to Google sign-in instead. Students and staff can also apply or register with their college account.
- These accounts are **external**. They get only the *Applicant* or *Alumni* role, which opens their own application or profile and nothing in the dashboard. They're listed separately under Users & access → *Applicants & alumni*, where a Super Admin can suspend one if needed.

## Admissions (for the Admission Officer)

### 1. Set up an intake

- **Dashboard → Intakes → Add intake**: give it a name (e.g. *Fall 2026*), when applications open and close (in Nepal time), and what applicants should know. Publish it.
- **Dashboard → Programmes on offer → Add programme**: choose the intake, then fill in the programme, seats, who can apply, and a note on fees. The order in the dashboard is the order on the Admissions page.

The intake appears on `/admissions` while it's open or opening soon, and applicants can apply between the two times.

### 2. What applicants do (`/apply`)

1. Sign in with their email.
2. Choose a programme, plus a second choice if they want one.
3. Fill in their details and previous study (school, board, year, GPA), and upload a **photo** and **transcript** (PDF). A **citizenship or passport** PDF is optional at first.
4. **Save draft** at any time and come back later. **Send application** checks that nothing required is missing.
5. They get a reference number (e.g. `NCIT-2026-00001`) and an email. Their page then shows the status, a timeline, and any message from the office.

### 3. Reviewing (Dashboard → Applications)

Filter by status or intake, or search by name, email or reference. Click an application to see everything, open the documents, and choose the **next step**:

| Step | Meaning | The applicant |
|---|---|---|
| Under review | You've started looking at it | is emailed (optional message) |
| Ask for more documents | Something is missing or unclear | is emailed your message (**required**) and can edit and send again |
| Accept | Offered a place | is emailed, e.g. with fee and enrolment dates |
| Waiting list | Not yet | is emailed |
| Don't accept | Not offered a place | is emailed |

- Untick **Email them** to change a status quietly, for example when correcting a mistake.
- The **Internal note** is for the office only and is never shown to the applicant.
- **Download CSV** exports the current filter, e.g. everyone accepted for one intake.
- Applicants can withdraw until a decision is made.

## Careers (for the HR Officer)

- **Dashboard → Vacancies → Add vacancy**: title, faculty or staff, employment type, positions, closing time, the role, requirements (one per line) and an optional job-description PDF. It shows on `/careers` until it closes.
- **Applying:** the applicant signs in with their email and sends their name, phone, qualification, experience, an optional note and a **CV (PDF)**. They're emailed a receipt and can withdraw while the application is open.
- **Reviewing:** use **Applicants** on a vacancy, or **Dashboard → Job applications**. Open the CV, then **Shortlist**, **Invite to interview** (the date, time and place are required and are emailed), **Make an offer** or **Don't take forward**. Internal notes and CSV export work as for admissions.

## Alumni (for the Alumni Coordinator)

1. **Registering:** a graduate signs in at `/alumni/join` and enters their name, programme, year of graduation and **Pokhara University registration number**, plus optionally what they do now, a photo and LinkedIn. They tick whether to appear in the directory, then send it.
2. **Verifying:** in **Dashboard → Alumni verification**, check the details against the college's records and choose:
   - **Verify:** they're emailed, and they appear in the directory if they agreed.
   - **Can't verify:** a reason is **required**. They're emailed it, can correct their details and send again.
3. **Home page:** tick **Feature on the home page** for verified alumni who agreed to be listed. The four most recently verified featured alumni replace the sample cards in the home page's Alumni section.
4. **Changes later:** if a verified alumnus edits a checked detail (name, programme, year or registration number), the profile goes back to *Waiting* for you to check again. Changing their job or city doesn't.

The public directory shows the name, programme, year, role, organisation, city, LinkedIn and photo. It **never** shows the email, phone or registration number.

## Emails (Super Admin → Email log)

Every email the website sends is listed here with its status:

| Status | Meaning |
|---|---|
| **Sent** | Handed to the mail server |
| **Recorded, not sent** | No mail server is configured yet (`SMTP_HOST` is empty). Normal on a laptop |
| **Failed** | The mail server refused it or was down. Open it and press **Send again** |

Sign-in code emails keep no code after sending. Applicants who didn't get one simply ask for a new code.

**Turning on real email:** fill in `.env`, then restart:

```
SMTP_HOST=smtp.your-provider.com
SMTP_PORT=587
SMTP_USER=…
SMTP_PASSWORD=…
MAIL_FROM=NCIT <no-reply@ncit.edu.np>
```

Use the college's mail server or a transactional email provider (e.g. Amazon SES, Mailgun or SendGrid). Set up SPF and DKIM for `ncit.edu.np` so the emails aren't marked as spam.

**Local testing without a mail server:** with `DEV_LOGIN=true`, the sign-in form shows the code on screen (marked *Development only*). `MAIL_KEEP_SENSITIVE=true` keeps codes readable in the Email log. Never use either in production.

**Demo accounts** (with `DEV_LOGIN=true`): `admissions.officer@`, `hr.officer@` and `alumni.coordinator@ncit.edu.np`.

## Documents are private

Transcripts, citizenship scans, photos sent with applications, and CVs are **not** public files:

- They're stored in a separate `private` volume, outside the public `/media` folder, which the gateway never serves.
- They're handed out only by the owning service, after checking the request comes from the applicant who uploaded them or from the officer for that area.
- They're sent with `Cache-Control: private, no-store`, so browsers and proxies don't keep copies.
- The office can open an application's documents only once it has been sent, never while it's still a draft.
- Like every upload, files are checked: photos are re-encoded (which removes hidden data such as location) and PDFs must be real PDFs, 10 MB at most.

## How it fits together

```
Browser ──► gateway (nginx)
              ├── /admissions, /apply, /careers, /careers/<slug>, /alumni, /alumni/join  → static pages
              ├── /api/v1/auth/code/...         → auth-service (email codes; tightly rate limited)
              ├── /api/v1/admissions/public/... → admission-service (cached: Redis, plus 5 s at the gateway)
              ├── /api/v1/admissions/me/...     → admission-service (the applicant's own application; rate limited)
              ├── /api/v1/admissions/...        → admission-service (Admission Officer)
              ├── /api/v1/careers/...           → career-service      (same three layers)
              ├── /api/v1/alumni/...            → alumni-service      (same three layers)
              └── /api/v1/notify/...            → notification-service (Email log, Super Admin)

Services ──► Redis stream "ncit:mail" ──► notification-worker ──► SMTP server (or "recorded" with none)
```

- **Mail queue:** services never talk to the mail server. They put a message on the `ncit:mail` stream, using `ncit_common.mail`, with a template name and its data. notification-service owns the wording of every email (`services/notification-service/app/templates.py`), sends them and keeps the log. This is a separate stream from the audit events, so sign-in codes never reach the audit log. If the mail server is down, applications are still saved and the email shows as *Failed*, ready to send again.
- **Databases:** `ncit_admissions` (intakes, offerings, applications, application history), `ncit_careers` (jobs, job applications), `ncit_alumni` (alumni profiles), `ncit_notify` (the Email log). auth-service gained a `one_time_codes` table (migration `0002`).
- **Front end:** `public/assets/js/portal.js` (code sign-in and API calls shared by all three portals), `admissions-pages.js`, `careers-pages.js`, `alumni-pages.js`, `home-portal.js` (featured alumni), `dashboard-review.js` (the four review screens), and the intake, programme and vacancy editors in `dashboard-content.js`.
- **Preview without a backend:** `npm run serve` uses `public/assets/data/portal-preview.json`. Signing in, applying and registering need the services. The dashboard demo mode has sample applications, a job application, an alumni registration and an email.

## API (through the gateway)

**auth-service:** `POST /api/v1/auth/code/request {email, purpose: applicant|alumni}`, then `POST /api/v1/auth/code/verify {email, code}`.

**admission-service**

| Method & path | Who | Purpose |
|---|---|---|
| `GET /public/intakes` | anyone | Open and upcoming intakes with their programmes |
| `GET` / `POST /me/applications` | signed in | My applications / start one `{offering_id}` |
| `GET` / `PATCH /me/applications/{id}` | owner | View / edit (only while a draft or when more documents were asked for) |
| `POST` / `GET /me/applications/{id}/documents/{photo\|transcript\|citizenship}` | owner | Upload / download a document |
| `POST /me/applications/{id}/submit` · `/withdraw` | owner | Send / withdraw |
| `GET`, `POST /intakes`, `/offerings`; `PATCH`, `DELETE …/{id}` | Admission Officer | Manage intakes and programmes |
| `GET /review/applications?status=&intake_id=&q=&page=` (`.csv` for a download) | Admission Officer | Sent applications, with counts by status |
| `GET /review/applications/{id}` | Admission Officer | Everything, including history and the internal note |
| `POST /review/applications/{id}/status {status, message, notify}` | Admission Officer | Next step (emails the applicant unless `notify: false`) |
| `PATCH /review/applications/{id}/note`; `GET …/documents/{doc}` | Admission Officer | Internal note; documents |

**career-service:** `GET /public/jobs`, `GET /public/jobs/{slug}`; signed in: `GET /me/applications`, `GET /me/jobs/{slug}`, `POST /me/jobs/{slug}/apply` (multipart with `cv`), `POST /me/jobs/{slug}/withdraw`; HR Officer: `/jobs` (CRUD), `GET /review/applications?job_id=&status=&q=` (`.csv`), `GET /review/applications/{id}`, `POST …/status`, `PATCH …/note`, `GET …/cv`.

**alumni-service:** `GET /public/directory?q=&programme=&year=&page=`, `GET /public/featured`; signed in: `GET` / `PUT /me/profile`, `POST /me/profile/photo`, `POST /me/profile/submit`; Alumni Coordinator: `GET /review/profiles?status=&q=` (`.csv`), `POST /review/profiles/{id}/status {status: verified|rejected, message}`, `PATCH /review/profiles/{id} {featured}`.

**notification-service:** Super Admin: `GET /messages?status=&q=&page=`, `GET /messages/{id}`, `POST /messages/{id}/retry`.

## Phase 5 gate: how it was checked

Gate: *apply, review, status email and alumni verification work end to end.*

| Part | Automated test | End to end (real PostgreSQL, Redis, nginx, the mail worker, a browser) |
|---|---|---|
| Apply → review → status email | `test_gate_apply_review_and_status_email` (admission-service) | An applicant signed in with an emailed code (a wrong code was refused with "4 tries left"), was told which required fields were missing, filled in the form, uploaded a photo and transcript, and sent it (reference NCIT-2026-00001). The Admission Officer opened the transcript (served as a private PDF), moved it to *Under review*, then *Accepted* with a message, and added an internal note. The applicant's page showed *Accepted*, the message and the timeline, and the Email log listed the receipt and both status emails. |
| Alumni verification | `test_gate_alumni_verification` (alumni-service) | A graduate registered at `/alumni/join`. The Alumni Coordinator verified and featured them; they were emailed and appeared in the directory. |
| Job applications | `test_apply_review_and_status_emails` (career-service) | An applicant applied with a CV. The HR Officer opened the CV and invited them to interview; without a time and place this was refused. The applicant was emailed. |
| Email codes | 6 tests in `tests/test_email_code.py` (auth-service) | Covered in the rows above |
| Emails | 6 tests (notification-service), including the worker on Redis and removal of codes | The mail worker took every email off the queue and recorded it |
| Roles kept apart | `test_only_admission_officers_review`, `test_only_hr_reviews_and_cv_is_required`, `test_privacy_and_roles` | Admission Officer, HR Officer and Alumni Coordinator each got 403 from the other areas' APIs; an applicant got 403 from the review API |
| Private documents | `test_applicants_see_only_their_own_and_documents_are_private`, `test_private_files_are_not_public` | Documents open only for their owner and the officer |

Also checked: no horizontal scrolling at phone width on every new page and in the dashboard; no script errors; the Phase 4 events and clubs flows still pass; the static preview and dashboard demo mode work with no backend.

Testing on the real PostgreSQL stack caught one bug the unit tests didn't: an empty "second choice" was sent to the database as text instead of NULL. It is fixed, and the tests now send an empty second choice too.
