# Website content (Phase 2)

Banners and ads, leadership messages, news, notices and facilities are edited in the dashboard by a **Super Admin** or a **Content Admin**, and served by **content-service**. Nobody edits HTML for them any more.

| What | Where it appears | Dashboard |
|---|---|---|
| **Banners & ads** | The rotating banner at the top of the home page | Website content → Banners & ads |
| **Leadership messages** | Home page (short quote) and `/leadership` (full message) | Website content → Leadership messages |
| **News** | Home page (latest 4), `/news`, and one page per article at `/news/<title>` | Website content → News |
| **Notices** | Home page (latest 5, pinned first) and `/notices`, with category filters and PDF downloads | Website content → Notices |
| **Facilities** | Campus life on the home page | Website content → Facilities |

## Who can edit

- **Super Admin:** everything.
- **Content Admin:** website content only. Grant it in Users & access → Grant a role → *Content Admin*.
- Heads of Department and other roles can't see or change website content.

Every change appears in the Audit log (filter "Banners", "News" and so on).

## Scheduling

Times are entered in Nepal time.

| Item | Fields | Behaviour |
|---|---|---|
| Banner | **Show from** / **Show until** (both optional) | Appears and disappears by itself. Leave both empty to show it while it's published. |
| News article | **Publish at** (optional) | Empty means "now". A future time schedules the article. |
| Notice | **Publish at** / **Remove after** (optional) | Goes up and comes down by itself. **Pin to the top** keeps it first. |

Each item in the dashboard shows its status:
- **Live:** on the website now.
- **Scheduled:** published, but its start time hasn't come yet.
- **Expired:** its end time has passed.
- **Draft:** not published.

Use the filter buttons to see each group.

Changes reach the website within about 5 seconds. Public pages are cached in Redis to keep the site fast, and every change clears that cache at once ([CACHING-AND-NOTIFICATIONS.md](CACHING-AND-NOTIFICATIONS.md)).

## Tips

- **Banner photos:** landscape, at least 2000 px wide. The headline sits in the lower left, so keep that part of the photo calm. Fill in the photo description for screen-reader users.
- **Notice PDFs:** up to 10 MB. Exam routines and results usually work best as a PDF attached to a short title. Use **Or a link** for results published on another site (e.g. Pokhara University).
- **Text:** plain text. Leave a blank line between paragraphs. HTML or other formatting codes are shown as typed, never run.
- **Leadership:** there is exactly one message each for the Executive Director, Director and Principal. Edit the existing one; untick **Published** to hide it.
- **Order:** banners, leadership messages and facilities appear in the order shown in the dashboard (use the arrows). News and notices are newest first.

## What changed for the home page

The home page loads banners, news, notices, leadership and facilities from content-service in one request (`/api/v1/content/public/home`). The HTML still contains the original content as a fallback, so the page reads normally if the service is briefly down.

The starting content (seeded on first start) is what the home page showed before. Invented items are marked **(sample)**; the leadership names are the real ones. Replace the samples from the dashboard.

## How it fits together

```
Browser ──► gateway (nginx)
              ├── /, /news, /news/<slug>, /notices, /leadership  → static pages (news.html serves every article)
              ├── /api/v1/content/public/...   → content-service (cached: Redis, plus 5 s at the gateway)
              ├── /api/v1/content/...          → content-service (editing; JWT + CSRF; Super Admin / Content Admin)
              └── /media/content/...           → uploaded photos and PDFs (shared volume)
```

- **Service:** `services/content-service/` (Flask, its own PostgreSQL database `ncit_content`, Alembic migration, `flask --app wsgi seed` on start, which only fills empty collections).
- **Shared code:** field validation and upload handling live in `libs/ncit-common` (`ncit_common.fields`, `ncit_common.media`) and are used by both academics-service and content-service.
- **Front end:** `public/assets/js/home-content.js` (home page), `content-pages.js` (News, Notices, Leadership), `dashboard-content.js` (editor).
- **Preview without a backend:** `npm run serve` uses `public/assets/data/content-preview.json` and shows a "Preview" banner on the content pages; the dashboard runs in demo mode.

## API (through the gateway)

| Method & path | Who | Purpose |
|---|---|---|
| `GET /api/v1/content/public/home` | anyone | Live banners, leadership, latest news and notices, facilities |
| `GET /api/v1/content/public/news?page=` | anyone | Live news, newest first |
| `GET /api/v1/content/public/news/{slug}` | anyone | One live article |
| `GET /api/v1/content/public/notices?category=&page=` | anyone | Live notices, pinned first |
| `GET /api/v1/content/public/leadership` | anyone | Published leadership messages |
| `GET /api/v1/content/{collection}?status=&q=` | Super Admin / Content Admin | All items with their status; collection = `banners`, `leadership`, `news`, `notices`, `facilities` |
| `POST /api/v1/content/{collection}` | Super Admin / Content Admin | Create |
| `PATCH` / `DELETE /api/v1/content/{collection}/{id}` | Super Admin / Content Admin | Edit or delete |
| `POST /api/v1/content/{collection}/order` | Super Admin / Content Admin | Reorder (banners, leadership, facilities): `{ids: [...]}` |
| `POST /api/v1/content/uploads` | Super Admin / Content Admin | Multipart `file`, `kind` = `image` or `pdf`, `group` = collection; returns `{url}` |

## Phase 2 gate: how it was checked

| Gate | Automated test | End to end (real PostgreSQL, Redis, nginx, browser) |
|---|---|---|
| Super Admin schedules a banner | `test_gate_schedule_a_banner`: a scheduled banner is hidden until its start, shown during its window, hidden after its end | A banner with a photo, shown from an hour ago, appeared on the home page; a banner scheduled for tomorrow showed as **Scheduled** and stayed off the site |
| Super Admin publishes a message | `test_gate_publish_a_leadership_message` | The Principal's full message, edited and saved, appeared on `/leadership` |
| Notices with PDFs | `test_uploads`, `test_notices_pinned_first_and_expiry` | A pinned exam notice with a PDF topped the home page and `/notices`; the PDF downloaded as `application/pdf` |
| Roles | `test_content_admin_can_edit_but_hod_cannot` | A Content Admin saw only the website-content menu; an HOD got 403 |
