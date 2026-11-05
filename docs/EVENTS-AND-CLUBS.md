# Events, ECA and clubs (Phase 4)

Events and clubs are run from the dashboard by two separate roles, and served by two services:

| What | Run by | Service | On the website |
|---|---|---|---|
| **Events**: calendar, registration, waiting lists, attendance | **Event Admin** | event-service | `/events` (Upcoming · Past · Month calendar), `/events/<name>`, "Upcoming events" on the home page |
| **Clubs**: club pages, join requests, members, committee, activities | **ECA Admin** | eca-service | `/clubs`, `/clubs/<name>`, "ECA & clubs" on the home page |

A **Super Admin** can do both. An Event Admin can't see or change clubs, and an ECA Admin can't see or change events. This is the Phase 4 gate, checked by tests and in the browser (see the end of this page).

Students and staff don't need a role: any `@ncit.edu.np` account can register for events and ask to join clubs from the public pages, and sees what they signed up for under **My activity** in the dashboard.

## Giving someone the role

Users & access → **Grant a role** → *Event Admin* or *ECA Admin* → their college email. They get it the next time they sign in (or immediately, if they're already signed in, after a reload).

For local testing with `DEV_LOGIN=true`, the login page lists demo accounts: `event.admin@ncit.edu.np`, `eca.admin@ncit.edu.np`, `content.admin@ncit.edu.np`. Any other college address signs in as a student, e.g. `student.demo@ncit.edu.np`.

## Events (for Event Admins)

Dashboard → **Events** → **Add event**.

| Field | Notes |
|---|---|
| Event name, summary, details | Plain text; leave a blank line between paragraphs. |
| Category | Academic, Technical, Workshop, Seminar, Cultural, Sports, Career, General. Visitors filter by it. |
| Starts / Ends | **Nepal time**. Without an end time the event counts as 3 hours long. Multi-day events show on every day of the calendar. |
| Venue, Organised by | Shown on the event page and in lists. |
| Cover photo, Programme PDF, External link | Optional. Photos are resized and cleaned automatically; PDFs up to 10 MB. |
| **Take registrations** | Off = "No registration needed, just come along". On = signed-in students and staff can register. |
| **Places** | 0 = no limit. When the places are taken, new sign-ups join a **waiting list**. |
| **Registration closes** | Optional; empty = when the event starts. |

Each event shows a status: **Upcoming**, **On now**, **Past** or **Draft** (not published). A published event appears on the website within about 5 seconds.

### Registrations

Click **Registrations** on an event to see who signed up.

- **Attended:** tick it on the day; the count appears at the top.
- **Cancel:** frees the place. The first person on the waiting list moves up automatically.
- **Admit:** moves someone off the waiting list even if the event is full (you decide to make room).
- **Restore:** brings back a cancelled registration.
- **Download CSV:** the full list for Excel (name, email, status, attended, when they registered).

Adding places to a full event also moves people up from the waiting list automatically. Students see their status on the event page ("You're registered" or "You're number 2 on the waiting list") and under **My activity**.

## Clubs (for ECA Admins)

Dashboard → **Clubs**: add or edit a club (name, category, one-line description, about, when and where it meets, staff coordinator, photo and logo). **Accepting new members** turns the "Ask to join" button on or off. Use the arrows to set the order on the website.

### Join requests and members

1. A student opens a club page, signs in and clicks **Ask to join** (optionally saying why).
2. The request appears under **Join requests** (the menu shows how many are waiting) and under the club's **Members** button.
3. **Approve** or **Reject**. Rejected students can ask again later.
4. For approved members, type a **Committee position** (President, Secretary, Treasurer …) and press **Save**. Members with a position are listed as the club's **Committee** on its public page; other members are counted but not named.
5. **Remove** takes someone out of the club. Students can also leave, or withdraw a request, from the club page.

### Club activities

Dashboard → **Club activities** → **Add activity**: choose the club, a title, the date, what happened and a photo. Published activities appear on the club page and under "Recent club activities" on `/clubs`.

## Privacy

- Registration lists and membership requests are visible only to Event / ECA Admins and Super Admins.
- On the public site, events show only how many places are taken, never who took them. Clubs show only the member count and the committee members' names and positions.
- Every action (a student registering or asking to join, an admin approving, cancelling or marking attendance) is recorded in the **Audit log**. Filter by "Event registrations" or "Club memberships".

## How it fits together

```
Browser ──► gateway (nginx)
              ├── /events, /events/<slug>, /clubs, /clubs/<slug>  → static pages (event.html / club.html serve every event / club)
              ├── /api/v1/events/public/...   → event-service (cached: Redis, plus 5 s at the gateway)
              ├── /api/v1/events/me/...       → event-service (signed in: register, cancel, my registrations; rate limited)
              ├── /api/v1/events/...          → event-service (editing; Event Admin)
              ├── /api/v1/eca/public/...      → eca-service (cached: Redis, plus 5 s at the gateway)
              ├── /api/v1/eca/me/...          → eca-service (signed in: join, leave, my clubs; rate limited)
              ├── /api/v1/eca/...             → eca-service (editing; ECA Admin)
              └── /media/events/..., /media/eca/...  → uploaded photos and PDFs
```

- **Services:** `services/event-service/` (database `ncit_events`: `events`, `registrations`) and `services/eca-service/` (database `ncit_eca`: `clubs`, `activities`, `memberships`). Each has its own Alembic migration and seeds sample events or clubs (marked "(sample)") only into an empty database.
- **Shared code:** the editing routes (list, add, edit, delete, reorder, upload) are generated by `ncit_common.editor.editor_blueprint` from a description of each collection. content-service, event-service and eca-service all use it, so the three behave identically. Common columns and the UTC time type are in `ncit_common.models`.
- **Waiting list safety:** when someone registers or cancels, the event row is locked (`SELECT … FOR UPDATE`) while places are counted, so two people can't take the last place at the same moment.
- **Front end:** `public/assets/js/campus-pages.js` (Events, calendar, event page, Clubs, club page), `campus-shared.js` (Nepal-time formatting, API helpers), `home-campus.js` (home page), `dashboard-content.js` (event, club and activity editors), `dashboard-campus.js` (registrations, members, join requests, My activity).
- **Preview without a backend:** `npm run serve` uses `public/assets/data/campus-preview.json` with a "Preview" banner; registering and joining are disabled there. The dashboard demo mode includes sample registrations and a join request.

## API (through the gateway)

**event-service**

| Method & path | Who | Purpose |
|---|---|---|
| `GET /api/v1/events/public/events?when=upcoming\|past&category=&page=&limit=` | anyone | Published events |
| `GET /api/v1/events/public/events/{slug}` | anyone | One event, with `registration.state` = off / open / full / closed and places taken |
| `GET /api/v1/events/public/calendar?month=2026-12` | anyone | Events in a month (Nepal time) |
| `GET /api/v1/events/me/registrations` | signed in | My registrations |
| `GET /api/v1/events/me/events/{slug}` | signed in | My registration for one event |
| `POST` / `DELETE /api/v1/events/me/events/{slug}/register` | signed in | Register (or join the waiting list) / cancel |
| `GET`, `POST /api/v1/events/events`; `PATCH`, `DELETE /api/v1/events/events/{id}` | Event Admin | Manage events |
| `GET /api/v1/events/events/{id}/registrations` (`.csv` for a download) | Event Admin | Who registered |
| `PATCH /api/v1/events/events/{id}/registrations/{rid}` | Event Admin | `{attended}` or `{status: registered\|cancelled}` |
| `POST /api/v1/events/uploads` | Event Admin | Photo or PDF upload |

**eca-service**

| Method & path | Who | Purpose |
|---|---|---|
| `GET /api/v1/eca/public/clubs?category=` | anyone | Published clubs with member counts |
| `GET /api/v1/eca/public/clubs/{slug}` | anyone | One club with its committee and activities |
| `GET /api/v1/eca/public/activities?limit=` | anyone | Recent activities across clubs |
| `GET /api/v1/eca/me/memberships` | signed in | My clubs and requests |
| `GET /api/v1/eca/me/clubs/{slug}` | signed in | My membership of one club |
| `POST` / `DELETE /api/v1/eca/me/clubs/{slug}/join` | signed in | Ask to join `{message}` / withdraw or leave |
| `GET`, `POST /api/v1/eca/{clubs\|activities}`; `PATCH`, `DELETE /api/v1/eca/{clubs\|activities}/{id}`; `POST /api/v1/eca/clubs/order` | ECA Admin | Manage clubs and activities (`?club_id=` filters activities) |
| `GET /api/v1/eca/clubs/{id}/members` | ECA Admin | Members and requests of a club |
| `PATCH /api/v1/eca/clubs/{id}/members/{mid}` | ECA Admin | `{status: approved\|rejected\|left}` and/or `{position}` |
| `GET /api/v1/eca/requests/pending` | ECA Admin | Every waiting request, oldest first |
| `POST /api/v1/eca/uploads` | ECA Admin | Photo upload |

## Phase 4 gate: how it was checked

| Gate | Automated test | End to end (real PostgreSQL, Redis, nginx, browser) |
|---|---|---|
| Event Admin and ECA Admin can't edit each other's content | `test_gate_event_admin_and_eca_admin_are_separate` (event-service), `test_gate_eca_admin_and_event_admin_are_separate` (eca-service) | The Event Admin's menu showed only Events and My activity; their requests to the clubs and join-request APIs got 403. The ECA Admin's menu showed only Clubs, Join requests and Club activities; their attempt to create an event got 403. |
| Events calendar and registrations | `test_register_waitlist_and_promotion`, `test_more_places_move_the_waitlist_up`, `test_registration_closed_or_off`, `test_calendar_month`, `test_admin_registration_list_csv_and_attendance` | A student signed in, registered for a workshop from the event page and saw "You're registered". The Event Admin saw them in Registrations, ticked Attended and downloaded the CSV. A new event entered as 14:00 in the dashboard was stored as 14:00 Nepal time. |
| Clubs, members, activities | `test_join_approve_position_leave`, `test_rejected_can_ask_again_and_closed_clubs`, `test_activities_need_a_real_club_and_drafts_stay_hidden`, `test_delete_club_removes_members_and_activities` | The student asked to join the Robotics Club; the ECA Admin approved them from Join requests and made them Treasurer; the club page listed them in the Committee; the student's My activity showed "Robotics Club · Treasurer". A new club activity appeared on the club page. |
| Audited | event checks in the tests above | The Audit log listed the registration, attendance, approval, position change and new activity, each with who did it. |

Also checked: no horizontal scrolling at phone width on the events, calendar, event, club and dashboard pages; no script errors; the static preview and dashboard demo mode work with no backend.
