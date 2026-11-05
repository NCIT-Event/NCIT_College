# Go-live checklist and sign-off

The Phase 6 gate is **the college's sign-off**. This page lists everything that has to be true before ncit.edu.np switches to the new website, who does it, and where to tick it off. The technical work is done and tested ([LAUNCH-READINESS.md](LAUNCH-READINESS.md)); most of what remains is content and accounts that only the college can supply.

Status key: ☐ to do · ☑ done

## A. Content (college, using the dashboard)

Everything invented during the build is marked **Sample** on the page or **(sample)** in the text. None of it may go live.

| ☐ | What | Where | How many samples now |
|---|---|---|---|
| ☐ | NCIT logo file | `frontend/public/assets/img/ncit-logo.png` ([CONTENT-GUIDE.md](CONTENT-GUIDE.md)) | provisional |
| ☐ | Confirmed brand colours | `frontend/src/css/site.css`, one file | estimated from the logo |
| ☐ | Photos (campus, banners, leadership, alumni) | `frontend/public/assets/img/photos/` (see the README there) | most are placeholders |
| ☐ | Home banners | Dashboard → Banners & ads | 2 of 3 |
| ☐ | Leadership messages (full text and photos) | Dashboard → Leadership messages | 3 of 3 |
| ☐ | News articles | Dashboard → News | 4 |
| ☐ | Notices | Dashboard → Notices | 4 |
| ☐ | Facilities list and descriptions | Dashboard → Facilities | to confirm |
| ☐ | All 8 department pages: overview, HOD message, programmes, courses, faculty, labs, testimonials | Each HOD → My department | 16 sample faculty; sample text in every department |
| ☐ | Events | Event Admin → Events | 5 |
| ☐ | Clubs and activities | ECA Admin → Clubs, Club activities | 5 clubs |
| ☐ | Intake dates, programmes, seats, eligibility, fees | Admission Officer → Intakes, Programmes on offer | 8 programmes |
| ☐ | Vacancies (or none) | HR Officer → Vacancies | 3 |
| ☐ | Featured alumni (real, with consent) | Alumni Coordinator → verification | 4 sample profiles |
| ☐ | About page text: history and mission | `frontend/src/pages/about.html` | 1 paragraph |
| ☐ | Contact page: office hours | `frontend/src/pages/contact.html` | 1 line |
| ☐ | Privacy notice: retention periods and contact person, reviewed by the college | `frontend/src/pages/privacy.html` | 2 items |
| ☐ | Remove the "Design preview" banner at the top of every page | [CONTENT-GUIDE.md](CONTENT-GUIDE.md) §5 | |
| ☐ | A final search for "sample" on the live staging site returns nothing | `/search?q=sample` | |

Delete sample items rather than leaving them unpublished. The search for "sample" catches anything missed.

## B. Accounts and access (college IT and Super Admin)

| ☐ | Item |
|---|---|
| ☐ | Google OAuth client created by the NCIT Google Workspace admin; client ID and secret in `.env` ([PHASE-1-AUTH.md](PHASE-1-AUTH.md)) |
| ☐ | First Super Admin(s) in `SUPER_ADMIN_EMAILS`; at least **two** Super Admins, so one can't lock everyone out |
| ☐ | Roles granted: every HOD, Content Admin, Event Admin, ECA Admin, Admission Officer, HR Officer, Alumni Coordinator |
| ☐ | Each role holder has signed in once and done the training exercise for their role ([ADMIN-GUIDE.md](ADMIN-GUIDE.md)) |
| ☐ | Mail server settings in `.env` (`SMTP_…`), and **SPF and DKIM** records for the sending domain, so codes and status emails don't land in spam |
| ☐ | A test applicant received their sign-in code and status emails in a Gmail inbox, not the spam folder |
| ☐ | `CONTACT_EMAIL` set to a mailbox someone reads |

## C. Server (college IT)

| ☐ | Item | How to check |
|---|---|---|
| ☐ | Server meets the requirements; Docker installed | [OPERATIONS.md](OPERATIONS.md) §1 |
| ☐ | DNS for the domain points at the server; ports 80 and 443 open | `curl -I https://ncit.edu.np` |
| ☐ | Started with the HTTPS overlay; certificate issued | browser padlock; `strict-transport-security` header present |
| ☐ | `COOKIE_SECURE=true`, `DEV_LOGIN=false`, `MAIL_KEEP_SENSITIVE=false` | `grep -E "COOKIE_SECURE|DEV_LOGIN|MAIL_KEEP" .env` |
| ☐ | `.env` stored safely outside the server (password manager) | |
| ☐ | Nightly backup scheduled **and copied off the server** | [OPERATIONS.md](OPERATIONS.md) §4 |
| ☐ | One restore tested on a spare machine from a real backup | `infra/restore.sh` |
| ☐ | Uptime monitor watching `https://ncit.edu.np/api/health` and alerting someone | |
| ☐ | The campus's public internet address(es) listed in `gateway/campus-networks.conf`, so people on the college network aren't rate limited as one visitor | from campus: 20 quick sign-ins, none refused with 429 |
| ☐ | Security checks pass on the live server | `python3 tools/security_check.py https://ncit.edu.np` |
| ☐ | Load test on staging (or production before launch) | `python3 tools/load_test.py …` |
| ☐ | GitHub CI is green, including the weekly dependency scan | GitHub → Actions |
| ☐ | Sitemap submitted to Google Search Console | `https://ncit.edu.np/sitemap.xml` |

## D. Final walk-through (college and developer together, on the live address)

| ☐ | Check |
|---|---|
| ☐ | Every menu link and footer link opens a real page |
| ☐ | A department page, an event, a club, a vacancy and a news article each look right on a phone |
| ☐ | An applicant applies with a personal Gmail address, gets the code and the receipt email; the Admission Officer accepts the application; the applicant gets the email and sees "Accepted" |
| ☐ | A student registers for an event and asks to join a club; the admins see it |
| ☐ | A graduate registers; the Alumni Coordinator verifies them; they appear in the directory |
| ☐ | Site search finds a programme, a teacher and a notice |
| ☐ | A Contact-page message arrives in the `CONTACT_EMAIL` inbox |
| ☐ | A role removed in Users & access stops working at once |

## E. Sign-off

By signing, the college confirms that sections A to D are complete and that the new website can replace the current one at ncit.edu.np.

| Role | Name | Signature | Date |
|---|---|---|---|
| Executive Director or Principal | | | |
| Head of IT | | | |
| Content owner (Super Admin) | | | |
| Developer | | | |

**After go-live:**
- Keep the old site's server for two weeks in case anything needs comparing.
- Watch the Email log and Audit log daily for the first week.
- Review Users & access each semester.
