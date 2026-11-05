# Department pages

Every department has its own page at `/departments/<name>` (for example `/departments/computer`). Its content is entered in the dashboard and served by **academics-service**; nobody edits HTML.

| Department | Address |
|---|---|
| Computer Engineering | `/departments/computer` |
| Information Technology | `/departments/it` |
| Software Engineering | `/departments/software` |
| Information & Communication | `/departments/ice` |
| Civil Engineering | `/departments/civil` |
| Architecture | `/departments/architecture` |
| Computer Applications & Science | `/departments/bca` |
| Management | `/departments/management` |

## Starting content

All eight departments start with the **same kind of content**: a short introduction, an overview, an HOD message, the programmes, semester-1 courses, two faculty entries, two labs and one student testimonial. Every starter item is marked **(sample)**. Computer Engineering already has its real HOD (Er. Amit Kumar Shrivastava) and photo.

Each HOD replaces the sample items with real ones from the dashboard. Starter content is only added to departments that nobody has edited, and only to empty sections, so restarting the service never overwrites an HOD's work.

## Giving each HOD their sign-in

HODs sign in with their own `@ncit.edu.np` Google account; there are no separate passwords. A department is linked to its HOD in either of two ways:

- **Dashboard (any time):** a Super Admin opens Users & access → Grant a role → *Head of Department* → choose the department.
- **Settings file (set once, applied on every start):** in `.env`, list each department code with its HOD's email:
  ```
  HOD_ASSIGNMENTS=computer=amit.shrivastava@ncit.edu.np,civil=civil.hod@ncit.edu.np,it=it.hod@ncit.edu.np
  ```
  Department codes: `computer`, `it`, `software`, `ice`, `civil`, `architecture`, `bca`, `management`. The HOD gets the role the first time they sign in. Removing someone from this line does **not** remove their role; do that in the dashboard.

**Local testing without Google:** with `DEV_LOGIN=true` in `.env` (your own computer only), the service also creates demo HODs `hod.computer@ncit.edu.np`, `hod.civil@ncit.edu.np` … one per department. The login page lists them as buttons: click one, press **Sign in**, then open **My department**.

## Who can edit what

| Person | Can do |
|---|---|
| **Head of Department** (role *HOD* for one department) | Edit everything on **their own** department page: overview, HOD message and photo, programmes, semester courses, faculty, labs, testimonials; publish or hide the page |
| **Super Admin** | Everything above for **every** department, plus rename departments and add new ones |
| Everyone else | Read the published pages |

An HOD who opens another department, even with a hand-crafted request, gets "You can only edit your own department". Every change is recorded in the Audit log with who made it and when.

## Editing a department (for HODs)

1. Sign in at `/login.html` with your `@ncit.edu.np` account. A Super Admin must first give you the **Head of Department** role for your department (Dashboard → Users & access → Grant a role).
2. Open **My department** in the dashboard menu.
3. Use the tabs:

| Tab | What goes on the page |
|---|---|
| **Overview** | Short introduction (under the department name), overview text, a department photo, contact email, phone and office |
| **HOD message** | Your name, title, message and photo |
| **Programmes & courses** | Programmes (name, level, duration, eligibility, description, syllabus link). Under **Courses by semester**, choose a programme and semester, fill in code / title / credits, and press **Save semester** |
| **Faculty** | One entry per teacher: name, designation, subjects, email, photo. Use the ↑ ↓ buttons to set the order |
| **Labs** | Name, description, photo |
| **Testimonials** | Student name, programme and year, quote, photo. Only items marked **Shown** appear on the page. Add quotes only with the student's permission |

4. Press **Save changes** (or **Save semester** for courses). The page updates within about a minute, because the website caches it briefly.
5. **View page** opens the public page in a new tab.

Writing tips:
- Leave a **blank line between paragraphs**. Line breaks are kept; formatting codes (HTML, Markdown) are shown as plain text, never run.
- Sections with nothing in them (for example Labs) are hidden from the page until you add something.
- Photos: JPEG, PNG or WebP up to 8 MB. They are resized to at most 1600 px, converted to JPEG, and stripped of hidden data such as the GPS location from phone cameras. Portraits are cropped from the top, so keep faces in the upper half.

**Publish switch:** *Published* means the page is on the website. Switch it off to hide the page (for example while rewriting it); the dashboard keeps everything.

## Super Admin tasks

- **Edit any department:** Dashboard → **Departments**, then choose the department from the list at the top.
- **Rename a department:** Overview tab → Department name (Super Admins only).
- **Add a department:** **Add department** → name and web address (e.g. `mechanical`). It starts as a **draft**. Then:
  1. Add it to `DEPARTMENTS` in `services/auth-service/app/roles.py` (code `mechanical`, name `Mechanical Engineering`) and redeploy auth-service, so you can grant an HOD for it.
  2. Grant the HOD role in Users & access.
  3. Publish once the page is ready.
  4. Optional: add it to the Academics menu in `frontend/src/partials/header.html` (desktop and mobile lists). The home page list updates by itself.

## How it fits together

```
Browser ──► gateway (nginx)
              ├── /departments/<slug>            → frontend/public/department.html (one template)
              ├── /api/v1/academics/public/...   → academics-service (cached: Redis, plus 5 s at the gateway)
              ├── /api/v1/academics/...          → academics-service (editing; JWT + CSRF + role check)
              └── /media/academics/...           → uploaded photos (shared volume)
```

- **Template:** `frontend/src/pages/department.html` and `frontend/public/assets/js/department.js` render any department from the API.
- **Home page list:** `frontend/public/assets/js/departments-list.js` loads published departments. If the service is unreachable, the list built into the page stays.
- **Editor:** `frontend/public/assets/js/dashboard-departments.js`.
- **Service:** `services/academics-service/` (Flask, its own PostgreSQL database `ncit_academics`, Alembic migrations). On first start it creates the eight departments (`flask --app wsgi seed`; running it again changes nothing).
- **Preview without a backend:** `npm run serve` serves `/departments/<slug>` from `frontend/public/assets/data/departments-preview.json`, with a "Preview" banner.

## API (through the gateway)

| Method & path | Who | Purpose |
|---|---|---|
| `GET /api/v1/academics/public/departments` | anyone | Published departments (for menus and the home page) |
| `GET /api/v1/academics/public/departments/{slug}` | anyone | One published department with programmes, courses, faculty, labs, shown testimonials |
| `GET /api/v1/academics/departments` | signed in | Departments **you** can edit |
| `POST /api/v1/academics/departments` | Super Admin | Create `{name, slug}` (draft) |
| `GET /api/v1/academics/departments/{slug}` | HOD of it / Super Admin | Editor view, including drafts and hidden testimonials |
| `PATCH /api/v1/academics/departments/{slug}` | HOD of it / Super Admin | Change overview, contact, HOD fields, `published` (`name` is Super Admin only) |
| `POST /api/v1/academics/departments/{slug}/media` | HOD of it / Super Admin | Upload a photo (multipart `file`) and get back its URL |
| `POST /api/v1/academics/departments/{slug}/{kind}` | HOD of it / Super Admin | Add an item; `kind` is `programmes`, `faculty`, `labs` or `testimonials` |
| `PATCH` / `DELETE /api/v1/academics/departments/{slug}/{kind}/{id}` | HOD of it / Super Admin | Edit or remove an item |
| `POST /api/v1/academics/departments/{slug}/{kind}/order` | HOD of it / Super Admin | Reorder: `{ids: [...]}` |
| `PUT /api/v1/academics/departments/{slug}/programmes/{id}/semesters/{n}` | HOD of it / Super Admin | Replace one semester's courses: `{courses: [{code, title, credits}]}` |

## How it was checked

- 15 automated tests (`services/academics-service/tests/`): the HOD edits only their own department, only a Super Admin renames, validation messages, order, approval of testimonials, semester replacement, photo re-encoding and rejection of non-images, drafts hidden from the public, sign-in required.
- End to end with real PostgreSQL, Redis, nginx and a browser: the HOD signed in, edited the overview and HOD message, uploaded a photo, saved semester 1 courses, added and reordered faculty, added a lab and a testimonial, and the public page showed all of it. The HOD's attempt to edit Civil was refused (403). The Super Admin unpublished Management (the public page returned 404) and created Mechanical Engineering as a draft. The audit log listed every change.
