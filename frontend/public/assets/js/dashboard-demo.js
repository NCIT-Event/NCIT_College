// Demo backend for the dashboard when auth-service isn't running (static
// preview). Same URLs and JSON shapes as the real API; data lives in memory
// and resets on reload. All people here are samples.

const ROLES = [
  ["super_admin", "Super Admin", null], ["content_admin", "Content Admin", null],
  ["event_admin", "Event Admin", null], ["eca_admin", "ECA Admin", null],
  ["hod", "Head of Department", "dept"], ["admission_officer", "Admission Officer", null],
  ["hr_officer", "HR Officer", null], ["alumni_coordinator", "Alumni Coordinator", null],
  ["teacher", "Teacher", null], ["student", "Student", null],
].map(([code, name, scoped]) => ({ code, name, scoped }));

const DEPARTMENTS = [
  ["computer", "Computer Engineering"], ["it", "Information Technology"], ["software", "Software Engineering"],
  ["ice", "Information & Communication"], ["civil", "Civil Engineering"], ["architecture", "Architecture"],
  ["bca", "Computer Applications & Science"], ["management", "Management"],
].map(([code, name]) => ({ code, name }));

const ago = (days) => new Date(Date.now() - days * 86400000).toISOString();
const ahead = (days) => new Date(Date.now() + days * 86400000).toISOString();
let seq = 100;
const id = () => `demo-${++seq}`;

function grant(role, scope = "*", expires_at = null) {
  const r = ROLES.find((x) => x.code === role);
  const dept = DEPARTMENTS.find((d) => `dept:${d.code}` === scope);
  return { id: id(), role, role_name: r.name, scope, scope_label: dept?.name || "", expires_at };
}

const users = [
  { id: "demo-me", email: "admin@ncit.edu.np", name: "Super Admin (demo)", status: "active", last_login_at: ago(0), roles: [grant("super_admin")] },
  { id: id(), email: "hod.computer@ncit.edu.np", name: "Sample HOD", status: "active", last_login_at: ago(0.1), roles: [grant("hod", "dept:computer"), grant("teacher")] },
  { id: id(), email: "events@ncit.edu.np", name: "Sample Event Admin", status: "active", last_login_at: ago(1), roles: [grant("event_admin", "*", ahead(4))] },
  { id: id(), email: "eca@ncit.edu.np", name: "Sample ECA Head", status: "active", last_login_at: ago(3), roles: [grant("eca_admin", "*", ahead(3))] },
  { id: id(), email: "hod.civil@ncit.edu.np", name: "hod.civil", status: "invited", last_login_at: null, created_at: ago(9), roles: [grant("hod", "dept:civil")] },
  { id: id(), email: "teacher@ncit.edu.np", name: "Sample Teacher", status: "active", last_login_at: ago(0.2), roles: [grant("teacher")] },
  { id: id(), email: "student@ncit.edu.np", name: "Sample Student", status: "suspended", last_login_at: ago(50), roles: [grant("student")] },
  { id: id(), email: "admissions@ncit.edu.np", name: "Sample Admission Officer", status: "active", last_login_at: ago(0.05), roles: [grant("admission_officer")] },
];

const audit = [];
function log(type, data = {}) {
  audit.unshift({ id: id(), type, service: "auth-service", at: new Date().toISOString(),
    actor: { id: "demo-me", email: "admin@ncit.edu.np" }, entity: "user", entity_id: "", data, ip: "127.0.0.1" });
}
log("user.sign_in_refused", { email: "someone@gmail.com", reason: "wrong_domain" });
log("user.signed_in", { method: "google" });

const json = (status, body) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const fail = (status, code, message) => json(status, { error: { code, message } });

function routeUsers(params) {
  const q = (params.get("q") || "").toLowerCase();
  const role = params.get("role");
  const status = params.get("status");
  const page = Number(params.get("page") || 1);
  const per = Number(params.get("per_page") || 25);
  const list = users.filter((u) => (!q || u.email.includes(q) || u.name.toLowerCase().includes(q))
    && (!role || u.roles.some((r) => r.role === role)) && (!status || u.status === status));
  return json(200, { items: list.slice((page - 1) * per, page * per), total: list.length, page, per_page: per });
}

function addGrant(body) {
  const email = (body.email || "").trim().toLowerCase();
  if (!email.endsWith("@ncit.edu.np")) return fail(422, "wrong_domain", "Use an @ncit.edu.np address. Other accounts can't sign in to the dashboard.");
  const spec = ROLES.find((r) => r.code === body.role);
  if (!spec) return fail(422, "invalid_role", "Choose a role from the list.");
  const scope = spec.scoped === "dept" ? `dept:${body.scope}` : "*";
  let user = users.find((u) => u.email === email);
  const invited = !user;
  if (!user) {
    user = { id: id(), email, name: email.split("@")[0], status: "invited", last_login_at: null, created_at: new Date().toISOString(), roles: [] };
    users.unshift(user);
  }
  if (!user.roles.some((r) => r.role === body.role && r.scope === scope)) {
    user.roles.push(grant(body.role, scope, body.expires_at ? new Date(`${body.expires_at}T23:59:59+05:45`).toISOString() : null));
  }
  const g = user.roles.find((r) => r.role === body.role && r.scope === scope);
  log("role.granted", { email, role: g.role, role_name: g.role_name, scope_label: g.scope_label, invited });
  return json(201, { user, invited });
}

/* ---- departments (academics-service) ---- */
let depts = null;
async function departments() {
  if (!depts) {
    const data = await (await fetch("/assets/data/departments-preview.json")).json();
    depts = data.departments.map((d) => ({ ...d, published: true, updated_by: "preview data",
      testimonials: d.testimonials.map((t) => ({ approved: true, ...t })) }));
  }
  return depts;
}
const flat = (d, k, v) => {
  const map = { contact_email: ["contact", "email"], contact_phone: ["contact", "phone"], office: ["contact", "office"],
    hod_name: ["hod", "name"], hod_title: ["hod", "title"], hod_message: ["hod", "message"], hod_photo: ["hod", "photo"] };
  if (map[k]) d[map[k][0]][map[k][1]] = v; else d[k] = v;
};
const summary = (d) => ({ slug: d.slug, name: d.name, tagline: d.tagline, published: d.published, programmes: d.programmes.map((p) => p.name), updated_at: d.updated_at, can_edit: true });
const touch = (d) => { d.updated_at = new Date().toISOString(); d.updated_by = "admin@ncit.edu.np (demo)"; };

async function academics(p, method, body, options) {
  const all = await departments();
  if (p === "/academics/departments" && method === "GET") return json(200, { items: all.map(summary) });
  if (p === "/academics/departments" && method === "POST") {
    if (all.some((d) => d.slug === body.slug)) return fail(409, "slug_taken", "A department with that web address already exists.");
    const d = { slug: body.slug, name: body.name, tagline: "", overview: "", hero_photo: "", contact: { email: "", phone: "", office: "" },
      hod: { name: "", title: "", message: "", photo: "" }, programmes: [], faculty: [], labs: [], testimonials: [], published: false };
    touch(d); all.push(d);
    return json(201, { department: d });
  }
  let m = p.match(/^\/academics\/departments\/([^/]+)$/);
  if (m) {
    const d = all.find((x) => x.slug === m[1]);
    if (!d) return fail(404, "department_not_found", "That department doesn't exist.");
    if (method === "PATCH") { Object.entries(body).forEach(([k, v]) => flat(d, k, v)); touch(d); }
    return json(200, { department: d });
  }
  m = p.match(/^\/academics\/departments\/([^/]+)\/media$/);
  if (m) return json(201, { url: URL.createObjectURL(options.body.get("file")) });
  m = p.match(/^\/academics\/departments\/([^/]+)\/programmes\/([^/]+)\/semesters\/(\d+)$/);
  if (m) {
    const d = all.find((x) => x.slug === m[1]);
    const prog = d.programmes.find((x) => x.id === m[2]);
    const n = Number(m[3]);
    prog.semesters = prog.semesters.filter((s) => s.semester !== n);
    if (body.courses.length) prog.semesters.push({ semester: n, courses: body.courses.map((c) => ({ id: id(), semester: n, ...c })), total_credits: body.courses.reduce((t, c) => t + Number(c.credits || 0), 0) });
    prog.semesters.sort((a, b) => a.semester - b.semester);
    touch(d);
    return json(200, { item: prog });
  }
  m = p.match(/^\/academics\/departments\/([^/]+)\/(programmes|faculty|labs|testimonials)(?:\/([^/]+))?$/);
  if (m) {
    const d = all.find((x) => x.slug === m[1]);
    const list = d[m[2]];
    if (m[3] === "order") { d[m[2]] = body.ids.map((i) => list.find((x) => x.id === i)); touch(d); return json(200, { ok: true }); }
    if (method === "POST") {
      const item = { id: id(), ...body };
      if (m[2] === "programmes") Object.assign(item, { semesters: [], semester_count: (item.duration_years || 4) * 2 });
      list.push(item); touch(d);
      return json(201, { item });
    }
    const item = list.find((x) => x.id === m[3]);
    if (!item) return fail(404, "item_not_found", "That item was already removed.");
    if (method === "PATCH") { Object.assign(item, body); if (m[2] === "programmes") item.semester_count = item.duration_years * 2; touch(d); return json(200, { item }); }
    if (method === "DELETE") { d[m[2]] = list.filter((x) => x !== item); touch(d); return json(200, { ok: true }); }
  }
  return fail(404, "not_found", "Not available in demo mode.");
}

/* ---- website content (content-service) ---- */
let content = null;
async function contentStore() {
  if (!content) {
    const p = await (await fetch("/assets/data/content-preview.json")).json();
    const tag = (list) => list.map((x) => ({ published: true, updated_by: "preview data", ...x }));
    content = { banners: tag(p.home.banners), leadership: tag(p.home.leadership), facilities: tag(p.home.facilities),
      news: tag(p.news), notices: tag(p.notices) };
  }
  return content;
}
function contentStatus(kind, x) {
  const now = Date.now();
  if (!x.published) return "draft";
  const start = kind === "banners" ? x.start_at : x.publish_at;
  const end = kind === "banners" ? x.end_at : kind === "notices" ? x.expires_at : null;
  if (start && Date.parse(start) > now) return "scheduled";
  if (end && Date.parse(end) <= now) return "expired";
  return "live";
}
async function contentApi(p, method, body, options) {
  const store = await contentStore();
  if (p === "/content/uploads") return json(201, { url: URL.createObjectURL(options.body.get("file")) });
  const m = p.match(/^\/content\/(banners|leadership|news|notices|facilities)(?:\/([^/]+))?$/);
  if (!m) return fail(404, "not_found", "Not available in demo mode.");
  const [, kind, itemId] = m;
  const list = store[kind];
  const out = (x) => ({ ...x, status: contentStatus(kind, x) });
  if (!itemId && method === "GET") return json(200, { items: list.map(out) });
  if (itemId === "order") { store[kind] = body.ids.map((i) => list.find((x) => x.id === i)); return json(200, { ok: true }); }
  if (!itemId && method === "POST") {
    const item = { id: id(), updated_by: "admin@ncit.edu.np (demo)", ...body };
    if (kind === "news") item.slug = (body.title || "article").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
    if ((kind === "news" || kind === "notices") && item.published && !item.publish_at) item.publish_at = new Date().toISOString();
    list.unshift(item);
    return json(201, { item: out(item) });
  }
  const item = list.find((x) => x.id === itemId);
  if (!item) return fail(404, "item_not_found", "That item was already removed.");
  if (method === "PATCH") {
    Object.assign(item, body);
    if ((kind === "news" || kind === "notices") && item.published && !item.publish_at) item.publish_at = new Date().toISOString();
    return json(200, { item: out(item) });
  }
  if (method === "DELETE") { store[kind] = list.filter((x) => x !== item); return json(200, { ok: true }); }
  return fail(404, "not_found", "Not available in demo mode.");
}

/* ---- events and clubs (event-service, eca-service) ---- */
let campus = null;
async function campusStore() {
  if (!campus) {
    const p = await (await fetch("/assets/data/campus-preview.json")).json();
    const people = [["Sita Tamang", "sita.tamang"], ["Ram Shrestha", "ram.shrestha"], ["Anisha Karki", "anisha.karki"], ["Bibek Thapa", "bibek.thapa"]];
    const reg = (n, status, i) => ({ id: id(), name: people[n][0] + " (sample)", email: `${people[n][1]}@ncit.edu.np`, status, attended: false, created_at: ago(5 - i), waitlist_position: null });
    campus = {
      events: p.events.map((e) => ({ ...e, published: true, updated_by: "preview data", registration_open: e.registration.state !== "off",
        capacity: e.registration.capacity, registration_closes_at: null })),
      clubs: p.clubs.map((c) => ({ ...c, published: true, updated_by: "preview data", pending_count: 0 })),
      activities: p.activities.map((a) => ({ ...a, published: true, updated_by: "preview data", club_id: p.clubs.find((c) => c.slug === a.club?.slug)?.id })),
      regs: {}, members: {},
    };
    const ws = campus.events.find((e) => e.capacity === 30);
    if (ws) campus.regs[ws.id] = [reg(0, "registered", 0), reg(1, "registered", 1), reg(2, "registered", 2)];
    const rob = campus.clubs[0];
    if (rob) campus.members[rob.id] = [{ ...reg(3, "pending", 0), message: "Second year, I'd like to work on drones.", position: "", decided_by: "" },
      { ...reg(0, "approved", 1), position: "President", decided_by: "eca.admin@ncit.edu.np" }];
  }
  return campus;
}
function eventStatus(x) {
  if (!x.published) return "draft";
  const start = Date.parse(x.start_at), end = x.end_at ? Date.parse(x.end_at) : start + 3 * 3600e3;
  return start > Date.now() ? "upcoming" : end > Date.now() ? "ongoing" : "past";
}
async function campusApi(p, method, body, options) {
  const st = await campusStore();
  if (p === "/events/uploads" || p === "/eca/uploads") return json(201, { url: URL.createObjectURL(options.body.get("file")) });
  const counts = (e) => { const r = st.regs[e.id] || []; return { registered_count: r.filter((x) => x.status === "registered").length, waitlist_count: r.filter((x) => x.status === "waitlisted").length }; };
  const club = (c) => { const m = st.members[c.id] || []; return { ...c, status: c.published ? "live" : "draft", member_count: m.filter((x) => x.status === "approved").length, pending_count: m.filter((x) => x.status === "pending").length }; };
  const out = { events: (e) => ({ ...e, ...counts(e), status: eventStatus(e) }), clubs: club,
    activities: (a) => ({ ...a, status: a.published ? "live" : "draft", club: st.clubs.find((c) => c.id === a.club_id) || null }) };
  if (p === "/events/me/registrations") return json(200, { items: Object.entries(st.regs).flatMap(([eid, list]) => list.filter((r) => r.email.startsWith("sita")).map((r) => ({ ...r, event: st.events.find((e) => e.id === eid) }))) });
  if (p === "/eca/me/memberships") return json(200, { items: Object.entries(st.members).flatMap(([cid, list]) => list.filter((m) => m.email.startsWith("sita")).map((m) => ({ ...m, club: st.clubs.find((c) => c.id === cid) }))) });
  if (p === "/eca/requests/pending") return json(200, { items: Object.entries(st.members).flatMap(([cid, list]) => list.filter((m) => m.status === "pending").map((m) => ({ ...m, club: st.clubs.find((c) => c.id === cid) }))) });
  let m = p.match(/^\/events\/events\/([^/]+)\/registrations(?:\/([^/]+))?$/);
  if (m) {
    const ev = st.events.find((e) => e.id === m[1]);
    const list = (st.regs[m[1]] ??= []);
    if (m[2]) { const r = list.find((x) => x.id === m[2]); Object.assign(r, body); log("registrations.updated", { name: ev.title, email: r.email, fields: Object.keys(body) }); return json(200, { item: r }); }
    return json(200, { event: { id: ev.id, title: ev.title, capacity: ev.capacity }, items: list });
  }
  m = p.match(/^\/eca\/clubs\/([^/]+)\/members(?:\/([^/]+))?$/);
  if (m) {
    const c = st.clubs.find((x) => x.id === m[1]);
    const list = (st.members[m[1]] ??= []);
    if (m[2]) {
      const mem = list.find((x) => x.id === m[2]);
      if (body.position && mem.status !== "approved" && body.status !== "approved") return fail(422, "invalid_field", "Approve the member before giving them a position.");
      Object.assign(mem, body, body.status ? { decided_by: "admin@ncit.edu.np (demo)" } : {});
      if (body.status && body.status !== "approved") mem.position = "";
      log(`memberships.${{ approved: "approved", rejected: "rejected", left: "removed" }[body.status] || "updated"}`, { name: c.name, email: mem.email, position: mem.position });
      return json(200, { item: mem });
    }
    return json(200, { club: { id: c.id, name: c.name }, items: list });
  }
  m = p.match(/^\/(?:events|eca)\/(events|clubs|activities)(?:\/([^/]+))?$/);
  if (!m) return fail(404, "not_found", "Not available in demo mode.");
  const [, kind, itemId] = m;
  const list = st[kind];
  if (!itemId && method === "GET") return json(200, { items: list.map(out[kind]) });
  if (itemId === "order") { st[kind] = body.ids.map((i) => list.find((x) => x.id === i)); return json(200, { ok: true }); }
  if (!itemId && method === "POST") {
    const item = { id: id(), updated_by: "admin@ncit.edu.np (demo)", ...body };
    if (kind !== "activities") item.slug = (body.title || body.name || "item").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
    list.unshift(item);
    return json(201, { item: out[kind](item) });
  }
  const item = list.find((x) => x.id === itemId);
  if (!item) return fail(404, "item_not_found", "That item was already removed.");
  if (method === "PATCH") { Object.assign(item, body); return json(200, { item: out[kind](item) }); }
  if (method === "DELETE") { st[kind] = list.filter((x) => x !== item); return json(200, { ok: true }); }
  return fail(404, "not_found", "Not available in demo mode.");
}

/* ---- admissions, careers, alumni, email log (Phase 5) ---- */
let p5 = null;
async function p5Store() {
  if (p5) return p5;
  const pv = await (await fetch("/assets/data/portal-preview.json")).json();
  const intake = pv.intakes.items[0];
  const t = (d) => ago(d);
  const offer = (i) => intake.offerings[i];
  const appl = (n, name, email, status, oi, grade, days) => ({
    id: id(), reference: `NCIT-2026-0000${n}`, full_name: `${name} (sample)`, email, status, grade, submitted_at: t(days),
    programme: offer(oi).programme, intake: intake.name, offering: { id: offer(oi).id, programme: offer(oi).programme }, second_choice: null,
    intake_obj: intake, date_of_birth: "2007-05-02", gender: "", phone: "98410000" + n, address: "Lalitpur", guardian_name: "Guardian (sample)", guardian_phone: "",
    school: "A higher secondary school (sample)", board: "NEB", passed_year: "2025", entrance_score: "", documents: { photo: true, transcript: true, citizenship: false },
    message: "", officer_note: "", history: [{ at: t(days), status: "submitted", by: email, message: "", emailed: true }],
  });
  p5 = {
    intakes: [{ ...intake, published: true, offering_count: intake.offerings.length, updated_by: "preview data" }],
    offerings: intake.offerings.map((o) => ({ ...o, published: true, status: "live", intake: intake.name, intake_id: intake.id })),
    jobs: pv.jobs.map((j) => ({ ...j, published: true, application_count: 1, new_count: 1 })),
    applications: [appl(1, "Sita Tamang", "sita.applicant@gmail.com", "submitted", 0, "3.6", 2), appl(2, "Bibek Thapa", "bibek.applicant@gmail.com", "under_review", 4, "3.2", 4)],
    jobApps: [{ id: id(), full_name: "Anisha Karki (sample)", email: "anisha@gmail.com", phone: "9841000009", status: "submitted", job: pv.jobs[0].title, job_id: pv.jobs[0].id,
      qualification: "ME Computer, TU", experience_years: "3", cover_letter: "Sample cover letter.", has_cv: false, created_at: t(1), message: "", hr_note: "", history: [] }],
    alumni: [{ id: id(), full_name: "Ram Shrestha (sample)", email: "ram.alum@gmail.com", phone: "", programme: "BE Computer Engineering", graduation_year: "2016",
      registration_no: "2012-1-32-0456", current_role: "Backend engineer", employer: "A software company", city: "Kathmandu", country: "Nepal", linkedin_url: "", bio: "",
      show_in_directory: true, status: "pending", featured: false, review_note: "", submitted_at: t(1) },
      ...pv.directory.items.map((a) => ({ ...a, email: "sample@example.com", status: "verified", featured: true, show_in_directory: true, registration_no: "SAMPLE", submitted_at: t(30) }))],
    mail: [{ id: id(), to: "sita.applicant@gmail.com", template: "application_submitted", service: "admission-service", subject: "Application received: NCIT-2026-00001",
      status: "logged", error: "", attempts: 1, sensitive: false, created_at: t(2), sent_at: t(2), body: "Dear Sita,\n\nWe've received your application… (sample)" }],
  };
  return p5;
}
const ADM_MOVES = { submitted: ["under_review", "documents_requested", "accepted", "waitlisted", "rejected"], under_review: ["documents_requested", "accepted", "waitlisted", "rejected"],
  documents_requested: ["under_review", "rejected"], accepted: ["waitlisted", "rejected"], waitlisted: ["accepted", "rejected"], rejected: ["accepted", "waitlisted"] };
const JOB_MOVES = { submitted: ["shortlisted", "interview", "rejected"], shortlisted: ["interview", "offered", "rejected"], interview: ["offered", "rejected"], offered: ["rejected"], rejected: ["shortlisted"] };
function counted(items) { const c = {}; items.forEach((x) => { c[x.status] = (c[x.status] || 0) + 1; }); return c; }
async function p5Api(p, method, body, url) {
  const st = await p5Store();
  const q = (url.searchParams.get("q") || "").toLowerCase(), status = url.searchParams.get("status") || "";
  const match = (x) => (!status || x.status === status) && (!q || JSON.stringify(x).toLowerCase().includes(q));
  if (p === "/admissions/uploads" || p === "/careers/uploads") return json(201, { url: URL.createObjectURL(body?.get?.("file") || new Blob()) });
  if (p === "/admissions/review/applications") return json(200, { items: st.applications.filter(match), total: st.applications.filter(match).length, page: 1, per_page: 25, counts: counted(st.applications) });
  let m = p.match(/^\/admissions\/review\/applications\/([^/]+)(?:\/(status|note))?$/);
  if (m) {
    const a = st.applications.find((x) => x.id === m[1]);
    if (m[2] === "status") {
      if (body.status === "documents_requested" && !body.message) return fail(422, "message_required", "Tell the applicant what's needed.");
      a.history.push({ at: new Date().toISOString(), status: body.status, by: "admissions.officer@ncit.edu.np (demo)", message: body.message, emailed: body.notify });
      Object.assign(a, { status: body.status, message: body.message });
      log(`applications.${body.status}`, { name: a.reference, programme: a.programme, applicant: a.email, emailed: body.notify });
    }
    if (m[2] === "note") a.officer_note = body.officer_note;
    return json(200, { item: { ...a, intake: { name: a.intake }, moves: ADM_MOVES[a.status] || [] } });
  }
  if (p === "/careers/review/applications") return json(200, { items: st.jobApps.filter(match) });
  m = p.match(/^\/careers\/review\/applications\/([^/]+)(?:\/(status|note))?$/);
  if (m) {
    const a = st.jobApps.find((x) => x.id === m[1]);
    if (m[2] === "status") {
      if (body.status === "interview" && !body.message) return fail(422, "message_required", "Give the interview date, time and place.");
      a.history.push({ at: new Date().toISOString(), status: body.status, by: "hr.officer@ncit.edu.np (demo)", message: body.message });
      Object.assign(a, { status: body.status, message: body.message });
    }
    if (m[2] === "note") a.hr_note = body.hr_note;
    return json(200, { item: { ...a, job: { id: a.job_id, title: a.job }, moves: JOB_MOVES[a.status] || [] } });
  }
  if (p === "/alumni/review/profiles") return json(200, { items: st.alumni.filter(match), counts: counted(st.alumni) });
  m = p.match(/^\/alumni\/review\/profiles\/([^/]+)(?:\/(status))?$/);
  if (m) {
    const a = st.alumni.find((x) => x.id === m[1]);
    if (m[2] === "status") {
      if (body.status === "rejected" && !body.message) return fail(422, "message_required", "Tell the alumnus why, so they can correct it.");
      Object.assign(a, { status: body.status, review_note: body.status === "rejected" ? body.message : "" });
    } else if (body && "featured" in body) a.featured = body.featured;
    return json(200, { item: a });
  }
  if (p === "/notify/messages") return json(200, { items: st.mail.filter(match), total: st.mail.length, page: 1, per_page: 25, counts: counted(st.mail), smtp: false });
  m = p.match(/^\/notify\/messages\/([^/]+)$/);
  if (m) return json(200, { item: st.mail.find((x) => x.id === m[1]) });
  m = p.match(/^\/(?:admissions|careers)\/(intakes|offerings|jobs)(?:\/([^/]+))?$/);
  if (!m) return fail(404, "not_found", "Not available in demo mode.");
  const [, kind, itemId] = m;
  const list = st[kind];
  const out = (x) => ({ ...x, status: kind === "offerings" ? (x.published ? "live" : "draft") : !x.published ? "draft"
    : kind === "intakes" && Date.parse(x.opens_at) > Date.now() ? "upcoming" : Date.parse(x.closes_at) > Date.now() ? "open" : "closed" });
  if (!itemId && method === "GET") return json(200, { items: list.map(out) });
  if (itemId === "order") { st[kind] = body.ids.map((i) => list.find((x) => x.id === i)); return json(200, { ok: true }); }
  if (!itemId && method === "POST") { const item = { id: id(), application_count: 0, new_count: 0, offering_count: 0, ...body }; list.unshift(item); return json(201, { item: out(item) }); }
  const item = list.find((x) => x.id === itemId);
  if (method === "PATCH") { Object.assign(item, body); return json(200, { item: out(item) }); }
  if (method === "DELETE") { st[kind] = list.filter((x) => x !== item); return json(200, { ok: true }); }
  return fail(404, "not_found", "Not available in demo mode.");
}

// the dashboard sends times without a zone, meaning Nepal time (as the real services read them)
const nepalTimes = (body) => body && Object.fromEntries(Object.entries(body).map(([k, v]) =>
  [k, typeof v === "string" && /^\d{4}-\d\d-\d\dT\d\d:\d\d$/.test(v) ? new Date(`${v}:00+05:45`).toISOString() : v]));

export async function demoFetch(path, options = {}) {
  const url = new URL(path, "http://demo");
  const method = (options.method || "GET").toUpperCase();
  const body = nepalTimes(options.json ?? null);
  const p = url.pathname;
  await new Promise((r) => setTimeout(r, 120)); // feel like a network

  if (p.startsWith("/academics/")) return academics(p, method, body, options);
  if (p.startsWith("/content/")) return contentApi(p, method, body, options);
  if (p.startsWith("/events/") || p.startsWith("/eca/")) return campusApi(p, method, body, options);
  if (/^\/(admissions|careers|alumni|notify)\//.test(p)) return p5Api(p, method, body ?? options.body, url);
  if (p === "/auth/me") return json(200, { user: users[0] });
  if (p === "/auth/roles") return json(200, { roles: ROLES, departments: DEPARTMENTS });
  if (p === "/auth/logout" || p === "/auth/refresh") return json(200, { ok: true });
  if (p === "/auth/users" && method === "GET") return routeUsers(url.searchParams);
  if (p === "/auth/users/summary") {
    const invited = users.filter((u) => u.status === "invited");
    const soon = Date.now() + 7 * 86400000;
    return json(200, {
      invited: invited.length,
      oldest_invite_days: invited.length ? Math.max(...invited.map((u) => Math.floor((Date.now() - new Date(u.created_at || Date.now())) / 86400000))) : null,
      expiring: users.flatMap((u) => u.roles.filter((r) => r.expires_at && new Date(r.expires_at) < soon)),
      suspended: users.filter((u) => u.status === "suspended").length,
    });
  }
  if (p === "/auth/users/grants" && method === "POST") return addGrant(body || {});
  if (p === "/auth/users/import") return fail(501, "demo", "CSV import needs the real backend.");

  let m = p.match(/^\/auth\/users\/([^/]+)\/grants\/([^/]+)$/);
  if (m && method === "DELETE") {
    const user = users.find((u) => u.id === m[1]);
    const g = user?.roles.find((r) => r.id === m[2]);
    if (!g) return fail(404, "grant_not_found", "That role was already removed.");
    if (g.role === "super_admin" && user.id === "demo-me") return fail(409, "self_revoke", "Ask another Super Admin to remove your own Super Admin role.");
    user.roles = user.roles.filter((r) => r !== g);
    log("role.revoked", { email: user.email, role: g.role, role_name: g.role_name, scope_label: g.scope_label });
    return json(200, { user });
  }
  m = p.match(/^\/auth\/users\/([^/]+)\/(suspend|reactivate)$/);
  if (m) {
    const user = users.find((u) => u.id === m[1]);
    if (!user) return fail(404, "user_not_found", "That user no longer exists.");
    if (m[2] === "suspend" && user.id === "demo-me") return fail(409, "self_suspend", "You can't suspend your own account.");
    user.status = m[2] === "suspend" ? "suspended" : (user.last_login_at ? "active" : "invited");
    log(m[2] === "suspend" ? "user.suspended" : "user.reactivated", { email: user.email });
    return json(200, { user });
  }
  if (p === "/audit/") {
    const q = (url.searchParams.get("q") || "").toLowerCase();
    const type = url.searchParams.get("type") || "";
    const list = audit.filter((e) => (!type || e.type.startsWith(type)) && (!q || JSON.stringify(e).toLowerCase().includes(q)));
    return json(200, { items: list.slice(0, 25), total: list.length, page: 1, per_page: 25 });
  }
  return fail(404, "not_found", "Not available in demo mode.");
}
