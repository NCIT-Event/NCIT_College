// Generic editor for dashboard-managed content. Each "kind" names the service
// that owns it and the roles that may edit it:
//   content-service (/api/v1/content/): banners & ads, leadership, news, notices, facilities  (Content Admin)
//   event-service   (/api/v1/events/):  events                                               (Event Admin)
//   eca-service     (/api/v1/eca/):     clubs, club activities                               (ECA Admin)
// Super Admins can edit everything. Kind-specific buttons (registrations,
// members) are handed to the `onAction` hook given to initContent.

import { initPhotos } from "./site.js";

let ctx; // { api, toast, toastError, esc, icon, drawers }
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const st = { kind: "", items: [], status: "", q: "", editing: null };

const NOTICE_LABELS = { exam: "Exam", admission: "Admission", holiday: "Holiday", result: "Result", general: "General" };
const POSITIONS = { executive_director: "Executive Director", director: "Director", principal: "Principal" };
const EVENT_CATEGORIES = { academic: "Academic", technical: "Technical", workshop: "Workshop", seminar: "Seminar", cultural: "Cultural", sports: "Sports", career: "Career", general: "General" };
const CLUB_CATEGORIES = { technical: "Technical", cultural: "Cultural", sports: "Sports", arts: "Arts", social: "Social", academic: "Academic" };
const CONTENT = ["super_admin", "content_admin"];
const EVENTS = ["super_admin", "event_admin"];
const ECA = ["super_admin", "eca_admin"];
const ADMISSIONS = ["super_admin", "admission_officer"];
const HR = ["super_admin", "hr_officer"];
const JOB_KIND = { faculty: "Faculty", staff: "Staff" };
const EMPLOYMENT = { full_time: "Full time", part_time: "Part time", contract: "Contract" };
let intakeOptions = []; // [[id, name]] for the programme form, loaded when Programmes opens
let clubOptions = []; // [[id, name]] for the activity form, loaded when Activities opens
const ICON_CHOICES = ["library", "monitor", "cpu", "flask-conical", "utensils", "bus", "trophy", "building-2", "graduation-cap", "users", "book-open", "globe"];

/* ---------- what each content type looks like in the editor ---------- */

const KINDS = {
  banners: {
    service: "content", roles: CONTENT,
    title: "Banners & ads",
    intro: "Slides in the home page banner. Set “Show from” and “Show until” to schedule a banner, an ad or an announcement; it appears and disappears by itself.",
    singular: "banner", ordered: true, statuses: ["live", "scheduled", "expired", "draft"],
    name: (x) => x.title,
    meta: (x) => scheduleText(x.start_at, x.end_at),
    thumb: (x) => x.image,
    fields: [
      { name: "title", label: "Headline", max: 160, required: true },
      { name: "subtitle", label: "Text under the headline", type: "textarea", rows: 3, max: 300 },
      { name: "image", label: "Banner photo", type: "photo", hint: "Landscape, at least 2000 px wide. Keep the lower-left calm: the headline sits there." },
      { name: "image_alt", label: "Photo description (for screen readers)", max: 200 },
      { name: "cta_label", label: "Main button text", max: 40, half: true },
      { name: "cta_url", label: "Main button link", max: 300, half: true, hint: "e.g. /#apply or https://…" },
      { name: "cta2_label", label: "Second button text", max: 40, half: true },
      { name: "cta2_url", label: "Second button link", max: 300, half: true },
      { name: "start_at", label: "Show from (optional)", type: "datetime", half: true },
      { name: "end_at", label: "Show until (optional)", type: "datetime", half: true },
    ],
  },
  leadership: {
    service: "content", roles: CONTENT,
    title: "Leadership messages",
    intro: "Messages from the Executive Director, Director and Principal. The short quote appears on the home page; the full message on the Leadership page.",
    singular: "message", ordered: true, statuses: ["live", "draft"], fixed: true,
    name: (x) => `${x.person_name}`,
    meta: (x) => POSITIONS[x.position] || x.position,
    thumb: (x) => x.photo,
    fields: [
      { name: "position", label: "Position", type: "select", options: Object.entries(POSITIONS), half: true, lockOnEdit: true },
      { name: "role_title", label: "Title shown under the name", max: 120, half: true },
      { name: "person_name", label: "Name", max: 120, required: true },
      { name: "excerpt", label: "Short quote for the home page", type: "textarea", rows: 3, max: 400 },
      { name: "message", label: "Full message", type: "textarea", rows: 10, max: 8000, hint: "Leave a blank line between paragraphs." },
      { name: "photo", label: "Portrait", type: "photo" },
    ],
  },
  news: {
    service: "content", roles: CONTENT,
    title: "News",
    intro: "Articles on the home page and the News page. Set “Publish at” to a future time to schedule an article.",
    singular: "news article", ordered: false, statuses: ["live", "scheduled", "draft"],
    name: (x) => x.title,
    meta: (x) => [x.category, x.publish_at ? `${x.status === "scheduled" ? "Publishes" : "Published"} ${fmt(x.publish_at)}` : ""].filter(Boolean).join(" · "),
    thumb: (x) => x.cover,
    link: (x) => `/news/${x.slug}`,
    fields: [
      { name: "title", label: "Headline", max: 200, required: true },
      { name: "summary", label: "Summary", type: "textarea", rows: 2, max: 400, hint: "One or two sentences shown in lists." },
      { name: "body", label: "Article", type: "textarea", rows: 12, max: 20000, hint: "Leave a blank line between paragraphs." },
      { name: "cover", label: "Cover photo", type: "photo" },
      { name: "cover_alt", label: "Photo description", max: 200 },
      { name: "category", label: "Category", max: 40, half: true, hint: "e.g. Student life" },
      { name: "publish_at", label: "Publish at (optional)", type: "datetime", half: true, hint: "Empty = when you publish." },
    ],
  },
  notices: {
    service: "content", roles: CONTENT,
    title: "Notices",
    intro: "Exam routines, admissions, holidays and results. Attach a PDF or a link. Pinned notices stay at the top; set “Remove after” to take a notice down automatically.",
    singular: "notice", ordered: false, statuses: ["live", "scheduled", "expired", "draft"],
    name: (x) => x.title,
    meta: (x) => [NOTICE_LABELS[x.category], x.pinned ? "Pinned" : "", x.attachment ? "PDF attached" : x.link_url ? "Link" : "",
      x.publish_at ? fmt(x.publish_at) : "", x.expires_at ? `until ${fmt(x.expires_at)}` : ""].filter(Boolean).join(" · "),
    link: () => "/notices",
    fields: [
      { name: "title", label: "Title", max: 200, required: true },
      { name: "category", label: "Category", type: "select", options: Object.entries(NOTICE_LABELS), half: true },
      { name: "pinned", label: "Pin to the top", type: "checkbox", half: true },
      { name: "body", label: "Details (optional)", type: "textarea", rows: 4, max: 4000 },
      { name: "attachment", label: "PDF (optional)", type: "pdf" },
      { name: "link_url", label: "Or a link (optional)", max: 300, hint: "e.g. https://pu.edu.np/results" },
      { name: "publish_at", label: "Publish at (optional)", type: "datetime", half: true },
      { name: "expires_at", label: "Remove after (optional)", type: "datetime", half: true },
    ],
  },
  facilities: {
    service: "content", roles: CONTENT,
    title: "Facilities",
    intro: "The facilities listed in Campus life on the home page.",
    singular: "facility", ordered: true, statuses: ["live", "draft"],
    name: (x) => x.name,
    meta: (x) => (x.description || "").slice(0, 90),
    thumb: (x) => x.photo,
    fields: [
      { name: "name", label: "Name", max: 120, required: true },
      { name: "icon", label: "Icon", type: "select", options: ICON_CHOICES.map((i) => [i, i.replace(/-/g, " ")]) },
      { name: "description", label: "Description (optional)", type: "textarea", rows: 3, max: 1000 },
      { name: "photo", label: "Photo (optional)", type: "photo" },
    ],
  },
  events: {
    service: "events", roles: EVENTS,
    title: "Events",
    intro: "Events on the Events page, the calendar and the home page. Turn on registrations to let students and staff sign up with their college account; set a number of places to get a waiting list.",
    singular: "event", ordered: false, statuses: ["upcoming", "ongoing", "past", "draft"],
    name: (x) => x.title,
    meta: (x) => [fmt(x.start_at), x.venue, x.registration_open ? `${x.registered_count}${x.capacity ? `/${x.capacity}` : ""} registered${x.waitlist_count ? ` · ${x.waitlist_count} waiting` : ""}` : "No registration"].filter(Boolean).join(" · "),
    thumb: (x) => x.cover,
    link: (x) => `/events/${x.slug}`,
    linkStatuses: ["upcoming", "ongoing", "past"],
    actions: (x) => x.registration_open || x.registered_count ? [{ action: "registrations", icon: "users", label: `Registrations (${x.registered_count + x.waitlist_count})` }] : [],
    fields: [
      { name: "title", label: "Event name", max: 200, required: true },
      { name: "summary", label: "One-line summary", type: "textarea", rows: 2, max: 400 },
      { name: "category", label: "Category", type: "select", options: Object.entries(EVENT_CATEGORIES), half: true },
      { name: "organizer", label: "Organised by", max: 120, half: true, hint: "e.g. Department of IT" },
      { name: "start_at", label: "Starts", type: "datetime", half: true, required: true },
      { name: "end_at", label: "Ends (optional)", type: "datetime", half: true },
      { name: "venue", label: "Venue", max: 160 },
      { name: "body", label: "Details", type: "textarea", rows: 8, max: 12000, hint: "Leave a blank line between paragraphs." },
      { name: "cover", label: "Cover photo", type: "photo" },
      { name: "cover_alt", label: "Photo description", max: 200 },
      { name: "attachment", label: "Programme or brochure (PDF, optional)", type: "pdf" },
      { name: "external_url", label: "External link (optional)", max: 300 },
      { name: "registration_open", label: "Take registrations", type: "checkbox", half: true },
      { name: "capacity", label: "Places", type: "number", half: true, hint: "0 = no limit. When full, sign-ups join a waiting list." },
      { name: "registration_closes_at", label: "Registration closes (optional)", type: "datetime", hint: "Empty = when the event starts." },
    ],
  },
  clubs: {
    service: "eca", roles: ECA,
    title: "Clubs",
    intro: "Clubs on the ECA & clubs page. Students ask to join from the club page; you approve them under Members or Join requests.",
    singular: "club", ordered: true, statuses: ["live", "draft"],
    name: (x) => x.name,
    meta: (x) => [CLUB_CATEGORIES[x.category], `${x.member_count} member${x.member_count === 1 ? "" : "s"}`, x.join_open ? "" : "Not taking members"].filter(Boolean).join(" · "),
    thumb: (x) => x.photo || x.logo,
    link: (x) => `/clubs/${x.slug}`,
    actions: (x) => [{ action: "members", icon: "users", label: x.pending_count ? `Members · ${x.pending_count} waiting` : "Members", highlight: x.pending_count > 0 }],
    fields: [
      { name: "name", label: "Club name", max: 120, required: true },
      { name: "category", label: "Category", type: "select", options: Object.entries(CLUB_CATEGORIES), half: true },
      { name: "join_open", label: "Accepting new members", type: "checkbox", half: true },
      { name: "tagline", label: "One-line description", max: 300 },
      { name: "about", label: "About the club", type: "textarea", rows: 8, max: 6000, hint: "Leave a blank line between paragraphs." },
      { name: "meeting_info", label: "When and where the club meets", max: 200, hint: "e.g. Fridays 15:00 · Electronics lab" },
      { name: "coordinator_name", label: "Staff coordinator", max: 120, half: true },
      { name: "coordinator_email", label: "Coordinator email", max: 254, half: true },
      { name: "photo", label: "Cover photo", type: "photo" },
      { name: "photo_alt", label: "Photo description", max: 200 },
      { name: "logo", label: "Logo (optional)", type: "photo" },
    ],
  },
  activities: {
    service: "eca", roles: ECA,
    title: "Club activities",
    intro: "What clubs have been doing: workshops, trips, competition results. Shown on each club page and on the ECA & clubs page.",
    singular: "activity", ordered: false, statuses: ["live", "draft"], plural: "activities",
    name: (x) => x.title,
    meta: (x) => [x.club?.name, x.happened_on ? fmt(x.happened_on).split(",")[0] : ""].filter(Boolean).join(" · "),
    thumb: (x) => x.photo,
    link: (x) => (x.club ? `/clubs/${x.club.slug}` : ""),
    fields: [
      { name: "club_id", label: "Club", type: "select", options: () => clubOptions, required: true },
      { name: "title", label: "Title", max: 200, required: true },
      { name: "happened_on", label: "Date", type: "datetime" },
      { name: "body", label: "What happened", type: "textarea", rows: 6, max: 8000 },
      { name: "photo", label: "Photo (optional)", type: "photo" },
      { name: "photo_alt", label: "Photo description", max: 200 },
    ],
  },
  intakes: {
    service: "admissions", roles: ADMISSIONS,
    title: "Intakes",
    intro: "Admission rounds, such as Fall 2026. Applicants can apply between the opening and closing times; add the programmes on offer under Programmes on offer.",
    singular: "intake", ordered: false, statuses: ["open", "upcoming", "closed", "draft"],
    name: (x) => x.name,
    meta: (x) => `${fmt(x.opens_at)} → ${fmt(x.closes_at)} · ${x.offering_count} programme${x.offering_count === 1 ? "" : "s"}`,
    link: () => "/admissions", linkStatuses: ["open", "upcoming"],
    actions: (x) => [{ action: "intake-applications", icon: "inbox", label: "Applications" }],
    fields: [
      { name: "name", label: "Intake name", max: 120, required: true, hint: "e.g. Fall 2026" },
      { name: "opens_at", label: "Applications open", type: "datetime", half: true, required: true },
      { name: "closes_at", label: "Applications close", type: "datetime", half: true, required: true },
      { name: "intro", label: "What applicants should know", type: "textarea", rows: 6, max: 4000 },
    ],
  },
  offerings: {
    service: "admissions", roles: ADMISSIONS,
    title: "Programmes on offer",
    intro: "The programmes applicants can choose in each intake, with seats and eligibility. Shown on the Admissions page in this order.",
    singular: "programme", ordered: true, statuses: ["live", "draft"],
    name: (x) => x.programme,
    meta: (x) => [x.intake, x.seats ? `${x.seats} seats` : "", x.level === "master" ? "Master's" : "Bachelor's"].filter(Boolean).join(" · "),
    fields: [
      { name: "intake_id", label: "Intake", type: "select", options: () => intakeOptions, required: true },
      { name: "programme", label: "Programme", max: 160, required: true },
      { name: "level", label: "Level", type: "select", options: [["bachelor", "Bachelor's"], ["master", "Master's"]], half: true },
      { name: "seats", label: "Seats", type: "number", half: true },
      { name: "department", label: "Department code (optional)", max: 40, hint: "e.g. computer, civil, bca" },
      { name: "eligibility", label: "Who can apply", type: "textarea", rows: 4, max: 3000 },
      { name: "fee_note", label: "Fees", max: 300 },
    ],
  },
  jobs: {
    service: "careers", roles: HR,
    title: "Vacancies",
    intro: "Jobs on the Careers page. Applicants sign in with their email, attach a CV and follow their application; you review them under Job applications.",
    singular: "vacancy", plural: "vacancies", ordered: false, statuses: ["open", "closed", "draft"],
    name: (x) => x.title,
    meta: (x) => [JOB_KIND[x.kind], EMPLOYMENT[x.employment], `closes ${fmt(x.closes_at)}`, `${x.application_count} applied${x.new_count ? ` · ${x.new_count} new` : ""}`].filter(Boolean).join(" · "),
    link: (x) => `/careers/${x.slug}`, linkStatuses: ["open", "closed"],
    actions: (x) => [{ action: "job-applications", icon: "users", label: x.new_count ? `Applicants · ${x.new_count} new` : "Applicants", highlight: x.new_count > 0 }],
    fields: [
      { name: "title", label: "Job title", max: 200, required: true },
      { name: "kind", label: "Type", type: "select", options: Object.entries(JOB_KIND), half: true },
      { name: "employment", label: "Employment", type: "select", options: Object.entries(EMPLOYMENT), half: true },
      { name: "department", label: "Department or office", max: 120, half: true },
      { name: "positions", label: "Positions", type: "number", half: true },
      { name: "closes_at", label: "Applications close", type: "datetime", required: true },
      { name: "summary", label: "Summary", type: "textarea", rows: 2, max: 400 },
      { name: "description", label: "About the role", type: "textarea", rows: 8, max: 10000, hint: "Leave a blank line between paragraphs." },
      { name: "requirements", label: "Requirements", type: "textarea", rows: 5, max: 6000, hint: "One per line." },
      { name: "attachment", label: "Full job description (PDF, optional)", type: "pdf" },
    ],
  },
};

const STATUS = {
  live: ["tag-leaf", "Live"], scheduled: ["", "Scheduled"], expired: ["tag-amber", "Expired"], draft: ["tag-om", "Draft"],
  upcoming: ["tag-leaf", "Upcoming"], ongoing: ["tag-amber", "On now"], past: ["", "Past"],
  open: ["tag-leaf", "Open"], closed: ["", "Closed"],
};

/* ---------- helpers ---------- */

// Times are always shown and entered in Nepal time (UTC+05:45), whatever the editor's computer is set to.
const NPT_MS = 345 * 60000;
const MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const pad = (n) => String(n).padStart(2, "0");
const npt = (iso) => new Date(new Date(iso).getTime() + NPT_MS);
const fmt = (iso) => { const d = npt(iso); return `${d.getUTCDate()} ${MON[d.getUTCMonth()]} ${d.getUTCFullYear()}, ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`; };
function scheduleText(start, end) {
  if (!start && !end) return "Always shown while published";
  if (start && end) return `${fmt(start)} → ${fmt(end)}`;
  return start ? `From ${fmt(start)}` : `Until ${fmt(end)}`;
}
// <input type="datetime-local"> holds Nepal time; the server reads a time without a zone as Nepal time.
const toLocalInput = (iso) => (iso ? npt(iso).toISOString().slice(0, 16) : "");
const fromLocalInput = (v) => v || null;

const opts = (f) => (typeof f.options === "function" ? f.options() : f.options);
const api = (path, options) => ctx.api(`/${KINDS[st.kind].service}${path}`, options);
const plural = (spec) => spec.plural || `${spec.singular}s`;

function field(f, value, editing) {
  const { esc, icon } = ctx;
  const id = `cf-${f.name}`;
  const hint = f.hint ? `<p class="mt-1.5 text-[0.875rem] text-ink-3" id="${id}-hint">${esc(f.hint)}</p>` : "";
  const desc = f.hint ? `aria-describedby="${id}-hint"` : "";
  const label = `<label class="field-label" for="${id}">${esc(f.label)}</label>`;
  const wrap = (inner) => `<div class="${f.half ? "sm:col-span-1" : "sm:col-span-2"}">${inner}</div>`;
  const disabled = f.lockOnEdit && editing ? "disabled" : "";
  switch (f.type) {
    case "textarea":
      return wrap(`${label}<textarea id="${id}" name="${f.name}" rows="${f.rows || 4}" maxlength="${f.max}" class="field min-h-0 py-2.5 leading-relaxed" ${desc}>${esc(value)}</textarea>${hint}`);
    case "select":
      return wrap(`${label}<select id="${id}" name="${f.name}" class="field" ${desc} ${disabled}>${opts(f).map(([v, l]) => `<option value="${esc(v)}" ${String(value) === v ? "selected" : ""}>${esc(l)}</option>`).join("")}</select>${hint}`);
    case "checkbox":
      return wrap(`<label class="mt-8 flex cursor-pointer items-center gap-3 font-semibold"><input type="checkbox" name="${f.name}" class="h-5 w-5 accent-brand-700" ${value ? "checked" : ""}>${esc(f.label)}</label>`);
    case "number":
      return wrap(`${label}<input id="${id}" name="${f.name}" type="number" min="0" step="1" inputmode="numeric" value="${esc(value === "" || value == null ? 0 : value)}" class="field" ${desc}>${hint}`);
    case "datetime":
      return wrap(`${label}<input id="${id}" name="${f.name}" type="datetime-local" value="${esc(toLocalInput(value))}" class="field" ${desc}>${hint || `<p class="mt-1.5 text-[0.875rem] text-ink-3">Nepal time</p>`}`);
    case "photo":
    case "pdf": {
      const isPdf = f.type === "pdf";
      const preview = value ? (isPdf ? `<a class="font-semibold text-brand-700 underline" href="${esc(value)}" target="_blank" rel="noopener">View PDF</a>` : `<img src="${esc(value)}" alt="" class="h-full w-full object-cover">`) : icon(isPdf ? "file-text" : "camera", "icon");
      return wrap(`<span class="field-label">${esc(f.label)}</span>
        <div class="flex items-center gap-4" data-upload="${f.type}" data-name="${f.name}">
          <div class="flex ${isPdf ? "h-12 min-w-24 px-3" : "h-20 w-28"} flex-none items-center justify-center overflow-hidden rounded-sm bg-brand-100 text-brand-700" data-upload-preview>${preview}</div>
          <div class="flex flex-col items-start gap-1.5">
            <label class="btn btn-outline btn-sm cursor-pointer focus-within:outline-2 focus-within:outline-brand-600">${icon("download")}<span data-upload-label>${value ? "Replace" : "Upload"} ${isPdf ? "PDF" : "photo"}</span><input type="file" accept="${isPdf ? "application/pdf" : "image/jpeg,image/png,image/webp"}" class="sr-only" data-upload-input></label>
            <button type="button" class="text-[0.875rem] font-semibold text-om-700 hover:underline ${value ? "" : "hidden"}" data-upload-remove>Remove</button>
          </div>
          <input type="hidden" name="${f.name}" value="${esc(value)}">
        </div>${hint}`);
    }
    default:
      return wrap(`${label}<input id="${id}" name="${f.name}" type="text" maxlength="${f.max || 200}" value="${esc(value)}" class="field" ${desc}>${hint}`);
  }
}

function wireUploads(root) {
  $$("[data-upload]", root).forEach((box) => {
    const isPdf = box.dataset.upload === "pdf";
    const hidden = box.querySelector('input[type="hidden"]');
    const label = box.querySelector("[data-upload-label]");
    const remove = box.querySelector("[data-upload-remove]");
    const preview = box.querySelector("[data-upload-preview]");
    const set = (url) => {
      hidden.value = url;
      preview.innerHTML = url ? (isPdf ? `<a class="font-semibold text-brand-700 underline" href="${ctx.esc(url)}" target="_blank" rel="noopener">View PDF</a>` : `<img src="${ctx.esc(url)}" alt="" class="h-full w-full object-cover">`) : ctx.icon(isPdf ? "file-text" : "camera", "icon");
      label.textContent = `${url ? "Replace" : "Upload"} ${isPdf ? "PDF" : "photo"}`;
      remove.classList.toggle("hidden", !url);
    };
    box.querySelector("[data-upload-input]").addEventListener("change", async (e) => {
      const file = e.target.files[0];
      e.target.value = "";
      if (!file) return;
      const limit = isPdf ? 10 : 8;
      if (file.size > limit * 1024 * 1024) return ctx.toastError({ message: `That file is larger than ${limit} MB.` });
      label.textContent = "Uploading…";
      const body = new FormData();
      body.append("file", file);
      body.append("kind", isPdf ? "pdf" : "image");
      body.append("group", st.kind);
      try {
        const { url } = await api("/uploads", { method: "POST", body });
        set(url);
      } catch (err) {
        set(hidden.value);
        ctx.toastError(err);
      }
    });
    remove.addEventListener("click", () => set(""));
  });
}

/* ---------- list ---------- */

function render() {
  const spec = KINDS[st.kind];
  const { esc, icon } = ctx;
  const q = st.q.toLowerCase();
  const visible = st.items.filter((x) => (!st.status || x.status === st.status) && (!q || spec.name(x).toLowerCase().includes(q)));
  const counts = Object.fromEntries(spec.statuses.map((s) => [s, st.items.filter((x) => x.status === s).length]));
  $("[data-content-filters]").innerHTML = [["", `All (${st.items.length})`], ...spec.statuses.map((s) => [s, `${STATUS[s][1]} (${counts[s]})`])]
    .map(([s, l]) => `<button type="button" class="rounded-sm border px-3 py-1.5 text-[0.9375rem] font-semibold ${st.status === s ? "border-brand-700 bg-brand-50 text-brand-800" : "border-line text-ink-2 hover:border-brand-700"}" data-status="${s}" aria-pressed="${st.status === s}">${l}</button>`).join("");
  $("[data-content-list]").innerHTML = visible.length ? visible.map((x) => {
    const i = st.items.indexOf(x);
    const [cls, label] = STATUS[x.status] || ["", x.status];
    const thumb = spec.thumb ? (spec.thumb(x) ? `<div class="photo h-14 w-20 flex-none rounded-sm"><img src="${esc(spec.thumb(x))}" alt=""></div>` : `<span class="flex h-14 w-20 flex-none items-center justify-center rounded-sm bg-brand-100 text-brand-700">${icon(st.kind === "facilities" ? x.icon || "building-2" : "image", "icon")}</span>`) : "";
    const reorder = spec.ordered && !st.status && !q ? `
      <button type="button" class="btn btn-ghost h-9 w-9 px-0" data-cmove="${i}:-1" ${i === 0 ? "disabled" : ""} aria-label="Move ${esc(spec.name(x))} up">${icon("chevron-down", "icon-sm rotate-180")}</button>
      <button type="button" class="btn btn-ghost h-9 w-9 px-0" data-cmove="${i}:1" ${i === st.items.length - 1 ? "disabled" : ""} aria-label="Move ${esc(spec.name(x))} down">${icon("chevron-down")}</button>` : "";
    return `<li class="flex flex-wrap items-center gap-4 px-5 py-3.5 sm:flex-nowrap">
      ${thumb}
      <div class="min-w-0 flex-1 basis-[12rem]">
        <p class="font-semibold"><span class="tag ${cls} mr-2 align-[0.1em]">${label}</span>${esc(spec.name(x))}</p>
        <p class="truncate text-[0.9375rem] text-ink-2">${esc(spec.meta(x))}</p>
      </div>
      <div class="ml-auto flex flex-none items-center gap-1">
        ${reorder}
        ${(spec.actions ? spec.actions(x) : []).map((a) => `<button type="button" class="btn btn-ghost btn-sm ${a.highlight ? "text-om-700" : ""}" data-caction="${a.action}" data-id="${esc(x.id)}">${icon(a.icon)}<span>${esc(a.label)}</span></button>`).join("")}
        ${spec.link && spec.link(x) && (spec.linkStatuses || ["live"]).includes(x.status) ? `<a class="btn btn-ghost btn-sm" href="${esc(spec.link(x))}" target="_blank" rel="noopener" aria-label="View ${esc(spec.name(x))} on the website">${icon("arrow-up-right")}</a>` : ""}
        <button type="button" class="btn btn-ghost btn-sm" data-cedit="${esc(x.id)}">${icon("pencil")}<span>Edit</span></button>
        ${spec.fixed ? "" : `<button type="button" class="btn btn-ghost btn-sm text-om-700 hover:bg-om-50 hover:text-om-700" data-cdelete="${esc(x.id)}">Delete</button>`}
      </div>
    </li>`;
  }).join("") : `<li class="px-5 py-10 text-center text-ink-2">${st.items.length ? "Nothing matches this filter." : `No ${plural(spec)} yet.`}</li>`;
  initPhotos($("[data-content-list]"));
  $("[data-content-foot]").textContent = spec.ordered ? "Shown on the website in this order. Use the arrows to reorder." : "Newest first.";
}

async function load() {
  try {
    if (st.kind === "offerings") {
      const { items: intakes } = await ctx.api("/admissions/intakes");
      intakeOptions = intakes.map((x) => [x.id, x.name]);
    }
    if (st.kind === "activities") {
      const { items: clubs } = await ctx.api("/eca/clubs");
      clubOptions = clubs.map((c) => [c.id, c.name]);
    }
    const { items } = await api(`/${st.kind}`);
    st.items = items;
    render();
  } catch (err) { if (err.status !== 401) ctx.toastError(err); }
}

/* ---------- sheet ---------- */

function openSheet(item = null) {
  const spec = KINDS[st.kind];
  st.editing = item;
  $("[data-content-sheet-title]").textContent = `${item ? "Edit" : "Add"} ${spec.singular}`;
  if (st.kind === "activities" && !clubOptions.length) return ctx.toastError({ message: "Add a club first." });
  if (st.kind === "offerings" && !intakeOptions.length) return ctx.toastError({ message: "Add an intake first." });
  const blank = (f) => (f.type === "select" ? opts(f)[0]?.[0] ?? "" : f.type === "checkbox" ? f.name === "join_open" : f.type === "number" ? (f.name === "positions" ? 1 : 0) : "");
  $("[data-content-fields]").innerHTML = `<div class="grid gap-5 sm:grid-cols-2">${spec.fields.map((f) => field(f, item ? item[f.name] : blank(f), Boolean(item))).join("")}</div>`;
  $("[data-content-published]").checked = item ? item.published : true;
  $("[data-content-error]").classList.add("hidden");
  wireUploads($("[data-content-fields]"));
  $("[data-content-form]").scrollTop = 0;
  ctx.drawers.setOpen(document.getElementById("content-sheet"), true);
}

async function submit(e) {
  e.preventDefault();
  const spec = KINDS[st.kind];
  const form = $("[data-content-form]");
  const data = {};
  for (const f of spec.fields) {
    const el = form.elements[f.name];
    if (!el || el.disabled) continue;
    data[f.name] = f.type === "checkbox" ? el.checked : f.type === "datetime" ? fromLocalInput(el.value) : f.type === "number" ? Number(el.value || 0) : el.value;
  }
  data.published = $("[data-content-published]").checked;
  const error = $("[data-content-error]");
  const missing = spec.fields.find((f) => f.required && !String(data[f.name] || "").trim());
  if (missing) { error.textContent = `${missing.label} can't be empty.`; error.classList.remove("hidden"); return; }
  const btn = $("[data-content-submit]");
  btn.disabled = true;
  try {
    const id = st.editing?.id;
    const { item } = await api(`/${st.kind}${id ? `/${id}` : ""}`, { method: id ? "PATCH" : "POST", json: data });
    ctx.drawers.setOpen(document.getElementById("content-sheet"), false);
    await load();
    const when = { open: "It's on the website now (within a minute).", closed: "Its closing time has passed.", live: "It's on the website now (within a minute).", upcoming: "It's on the website now (within a minute).", ongoing: "It's on the website now.", past: "It's listed under past events.", scheduled: "It's scheduled and will appear by itself.", draft: "Saved as a draft, not on the website.", expired: "Its time window has passed, so it isn't shown." }[item.status];
    ctx.toast(`${ctx.icon("check")}<span>${ctx.esc(spec.name(item))} saved. ${when}</span>`);
  } catch (err) {
    error.textContent = err.message;
    error.classList.remove("hidden");
  } finally { btn.disabled = false; }
}

async function remove(id, button) {
  if (button.dataset.confirming !== "true") {
    button.dataset.confirming = "true";
    button.textContent = "Really delete?";
    setTimeout(() => { button.dataset.confirming = ""; button.textContent = "Delete"; }, 4000);
    return;
  }
  const item = st.items.find((x) => x.id === id);
  try {
    await api(`/${st.kind}/${id}`, { method: "DELETE" });
    await load();
    ctx.toast(`${ctx.icon("check")}<span>Deleted ${ctx.esc(KINDS[st.kind].name(item))}.</span>`);
  } catch (err) { ctx.toastError(err); }
}

async function move(index, delta) {
  const to = index + delta;
  if (to < 0 || to >= st.items.length) return;
  [st.items[index], st.items[to]] = [st.items[to], st.items[index]];
  render();
  $(`[data-cmove="${to}:${delta}"]`)?.focus();
  try {
    await api(`/${st.kind}/order`, { method: "POST", json: { ids: st.items.map((x) => x.id) } });
  } catch (err) { ctx.toastError(err); load(); }
}

/* ---------- public API ---------- */

export const CONTENT_VIEWS = Object.keys(KINDS);
export const contentTitle = (kind) => KINDS[kind]?.title || "Website content";
export const contentRoles = (kind) => KINDS[kind]?.roles || [];
export const reloadContent = () => load();

export function initContent(context) {
  ctx = context;
  $("[data-content-add]").addEventListener("click", () => openSheet());
  $("[data-content-form]").addEventListener("submit", submit);
  $("[data-content-search]").addEventListener("input", (e) => { st.q = e.target.value.trim(); render(); });
  document.addEventListener("click", (e) => {
    const f = e.target.closest("[data-status]");
    if (f && f.closest("[data-content-filters]")) { st.status = f.dataset.status; render(); return; }
    const ed = e.target.closest("[data-cedit]");
    if (ed) return openSheet(st.items.find((x) => x.id === ed.dataset.cedit));
    const del = e.target.closest("[data-cdelete]");
    if (del) return remove(del.dataset.cdelete, del);
    const act = e.target.closest("[data-caction]");
    if (act) return ctx.onAction?.(act.dataset.caction, st.items.find((x) => x.id === act.dataset.id));
    const mv = e.target.closest("[data-cmove]");
    if (mv) { const [i, d] = mv.dataset.cmove.split(":").map(Number); move(i, d); }
  });
}

export function showContent(kind) {
  const spec = KINDS[kind];
  st.kind = kind;
  st.status = "";
  st.q = "";
  $("[data-content-search]").value = "";
  $("[data-content-heading]").textContent = spec.title;
  $("[data-content-intro]").textContent = spec.intro;
  $("[data-content-add]").hidden = Boolean(spec.fixed);
  $("[data-content-add-label]").textContent = `Add ${spec.singular}`;
  $("[data-content-list]").innerHTML = `<li class="px-5 py-10 text-center text-ink-2">Loading…</li>`;
  load();
}
