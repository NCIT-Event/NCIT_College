// Reviewing what people send in: admission applications (Admission Officer),
// job applications (HR Officer), alumni registrations (Alumni Coordinator),
// and the Email log (Super Admin). One list + detail sheet, configured per view.

let ctx; // { api, toast, toastError, esc, icon, drawers }
const $ = (s, root = document) => root.querySelector(s);
const MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const pad = (n) => String(n).padStart(2, "0");
const npt = (iso) => new Date(new Date(iso).getTime() + 345 * 60000);
const day = (iso) => { if (!iso) return ""; const d = npt(iso); return `${d.getUTCDate()} ${MON[d.getUTCMonth()]} ${d.getUTCFullYear()}`; };
const when = (iso) => { if (!iso) return ""; const d = npt(iso); return `${day(iso)}, ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`; };

const ADMISSION = {
  submitted: ["", "Submitted", ""], under_review: ["", "Under review", "Start review"],
  documents_requested: ["tag-amber", "More documents needed", "Ask for more documents"],
  accepted: ["tag-leaf", "Accepted", "Accept"], waitlisted: ["tag-amber", "Waiting list", "Put on the waiting list"],
  rejected: ["tag-om", "Not accepted", "Don't accept"], withdrawn: ["", "Withdrawn", ""],
};
const JOB = {
  submitted: ["", "Received", ""], shortlisted: ["tag-leaf", "Shortlisted", "Shortlist"], interview: ["tag-leaf", "Interview", "Invite to interview"],
  offered: ["tag-leaf", "Offered", "Make an offer"], rejected: ["tag-om", "Not taken forward", "Don't take forward"], withdrawn: ["", "Withdrawn", ""],
};
const ALUMNI = { pending: ["tag-amber", "Waiting", ""], verified: ["tag-leaf", "Verified", "Verify"], rejected: ["tag-om", "Not verified", "Can't verify"] };
const MAIL = { sent: ["tag-leaf", "Sent", ""], logged: ["", "Recorded, not sent", ""], failed: ["tag-om", "Failed", ""] };
const DOC_LABEL = { photo: "Photo", transcript: "Transcript", citizenship: "Citizenship or passport" };

const VIEWS = {
  applications: {
    roles: ["super_admin", "admission_officer"], title: "Applications",
    intro: "Applications people have sent. Open one to see the details and documents, then move it along; the applicant is emailed each time, with your message.",
    labels: ADMISSION, statuses: ["submitted", "under_review", "documents_requested", "accepted", "waitlisted", "rejected", "withdrawn"],
    paged: true, base: "/admissions/review/applications", csv: "/api/v1/admissions/review/applications.csv",
    filter: { name: "intake_id", label: "All intakes", load: async () => (await ctx.api("/admissions/intakes")).items.map((x) => [x.id, x.name]) },
    row: (x) => ({ title: x.full_name || x.email, sub: [x.reference, x.programme, x.grade ? `GPA ${x.grade}` : ""].filter(Boolean).join(" · "), date: x.submitted_at }),
    detail: (id) => ctx.api(`/admissions/review/applications/${id}`).then((r) => r.item),
    sections: (a) => [
      ["Application", [["Reference", a.reference], ["Programme", a.offering.programme], ["Second choice", a.second_choice?.programme], ["Intake", a.intake.name], ["Sent", when(a.submitted_at)]]],
      ["Applicant", [["Name", a.full_name], ["Email", a.email], ["Mobile", a.phone], ["Date of birth", a.date_of_birth], ["Gender", a.gender], ["Address", a.address], ["Guardian", [a.guardian_name, a.guardian_phone].filter(Boolean).join(" · ")]]],
      ["Previous study", [["School", a.school], ["Board", a.board], ["Year passed", a.passed_year], ["GPA or percentage", a.grade], ["Entrance score", a.entrance_score]]],
    ],
    docs: (a) => Object.entries(a.documents).filter(([, v]) => v).map(([k]) => [DOC_LABEL[k], `/api/v1/admissions/review/applications/${a.id}/documents/${k}`]),
    move: (a, json) => ctx.api(`/admissions/review/applications/${a.id}/status`, { method: "POST", json }).then((r) => r.item),
    note: { field: "officer_note", save: (a, text) => ctx.api(`/admissions/review/applications/${a.id}/note`, { method: "PATCH", json: { officer_note: text } }) },
    messageHint: { documents_requested: "Say exactly what's missing. Required.", accepted: "e.g. fee payment dates and what to bring on enrolment day." },
  },
  "job-applications": {
    roles: ["super_admin", "hr_officer"], title: "Job applications",
    intro: "Applications for your vacancies. Download the CV, shortlist, invite to interview (include the time and place) or make an offer; the applicant is emailed each time.",
    labels: JOB, statuses: ["submitted", "shortlisted", "interview", "offered", "rejected", "withdrawn"],
    base: "/careers/review/applications", csv: "/api/v1/careers/review/applications.csv",
    filter: { name: "job_id", label: "All vacancies", load: async () => (await ctx.api("/careers/jobs")).items.map((x) => [x.id, x.title]) },
    row: (x) => ({ title: x.full_name, sub: [x.job, x.qualification].filter(Boolean).join(" · "), date: x.created_at }),
    detail: (id) => ctx.api(`/careers/review/applications/${id}`).then((r) => r.item),
    sections: (a) => [
      ["Application", [["Vacancy", a.job.title], ["Applied", when(a.created_at)]]],
      ["Applicant", [["Name", a.full_name], ["Email", a.email], ["Phone", a.phone], ["Qualification", a.qualification], ["Experience", a.experience_years ? `${a.experience_years} years` : ""]]],
      ["Cover letter", [["", a.cover_letter]]],
    ],
    docs: (a) => (a.has_cv ? [["CV", `/api/v1/careers/review/applications/${a.id}/cv`]] : []),
    move: (a, json) => ctx.api(`/careers/review/applications/${a.id}/status`, { method: "POST", json }).then((r) => r.item),
    note: { field: "hr_note", save: (a, text) => ctx.api(`/careers/review/applications/${a.id}/note`, { method: "PATCH", json: { hr_note: text } }) },
    messageHint: { interview: "Date, time and place of the interview. Required." },
  },
  "alumni-review": {
    roles: ["super_admin", "alumni_coordinator"], title: "Alumni verification",
    intro: "Check each registration against the college's records (name, programme, year and Pokhara University registration number). Verified alumni who agree appear in the directory; feature up to four on the home page.",
    labels: ALUMNI, statuses: ["pending", "verified", "rejected"],
    base: "/alumni/review/profiles", csv: "/api/v1/alumni/review/profiles.csv",
    row: (x) => ({ title: x.full_name, sub: [x.programme, x.graduation_year, x.registration_no ? `PU ${x.registration_no}` : "", x.featured ? "★ Featured" : ""].filter(Boolean).join(" · "), date: x.submitted_at }),
    detail: async (id) => st.items.find((x) => x.id === id),
    sections: (p) => [
      ["To check against records", [["Full name", p.full_name], ["Programme", p.programme], ["Year of graduation", p.graduation_year], ["PU registration number", p.registration_no]]],
      ["Contact (not public)", [["Email", p.email], ["Phone", p.phone]]],
      ["Now", [["Role", p.current_role], ["Organisation", p.employer], ["City", [p.city, p.country].filter(Boolean).join(", ")], ["LinkedIn", p.linkedin_url], ["About", p.bio], ["In the directory", p.show_in_directory ? "Yes, if verified" : "No"]]],
    ],
    moves: (p) => ({ pending: ["verified", "rejected"], verified: ["rejected"], rejected: ["verified"] })[p.status] || [],
    move: (p, json) => ctx.api(`/alumni/review/profiles/${p.id}/status`, { method: "POST", json }).then((r) => r.item),
    messageHint: { rejected: "Why it couldn't be verified, so they can correct it. Required." },
    extra: (p) => (p.status === "verified" && p.show_in_directory ? `<label class="mt-6 flex cursor-pointer items-center gap-3 font-semibold"><input type="checkbox" class="h-5 w-5 accent-brand-700" data-feature ${p.featured ? "checked" : ""}>Feature on the home page</label>` : ""),
  },
  "email-log": {
    roles: ["super_admin"], title: "Email log",
    intro: "Every email the website sent: sign-in codes, application updates, job and alumni notices. One-time codes are removed after sending.",
    labels: MAIL, statuses: ["sent", "logged", "failed"], paged: true, base: "/notify/messages", email: true,
    row: (x) => ({ title: x.subject, sub: `To ${x.to}${x.error ? ` · ${x.error}` : ""}`, date: x.created_at }),
    detail: (id) => ctx.api(`/notify/messages/${id}`).then((r) => r.item),
    sections: (m) => [["Email", [["To", m.to], ["Subject", m.subject], ["Sent by", m.service], ["Queued", when(m.created_at)], ["Sent", when(m.sent_at)], ["Attempts", String(m.attempts)], ["Error", m.error]]]],
    body: (m) => m.body,
    moves: () => [],
  },
};

const st = { view: "", items: [], status: "", q: "", filter: "", page: 1, total: 0, counts: {}, current: null };

/* ---------- list ---------- */

async function load() {
  const cfg = VIEWS[st.view];
  const params = new URLSearchParams();
  if (st.q) params.set("q", st.q);
  if (st.filter && cfg.filter) params.set(cfg.filter.name, st.filter);
  if (st.status && (cfg.paged || cfg.base.includes("alumni"))) params.set("status", st.status);
  if (cfg.paged) params.set("page", st.page);
  try {
    const data = await ctx.api(`${cfg.base}?${params}`);
    st.items = data.items;
    st.total = data.total ?? data.items.length;
    st.counts = data.counts || {};
    if (!data.counts) cfg.statuses.forEach((s) => { st.counts[s] = data.items.filter((x) => x.status === s).length; });
    st.smtp = data.smtp;
    render();
  } catch (err) { if (err.status !== 401) ctx.toastError(err); }
}

function render() {
  const cfg = VIEWS[st.view];
  const { esc, icon } = ctx;
  const all = Object.values(st.counts).reduce((a, b) => a + b, 0);
  $("[data-review-filters]").innerHTML = [["", `All (${all})`], ...cfg.statuses.map((s) => [s, `${cfg.labels[s][1]} (${st.counts[s] || 0})`])]
    .map(([s, l]) => `<button type="button" class="rounded-sm border px-3 py-1.5 text-[0.9375rem] font-semibold ${st.status === s ? "border-brand-700 bg-brand-50 text-brand-800" : "border-line text-ink-2 hover:border-brand-700"}" data-rstatus="${s}" aria-pressed="${st.status === s}">${l}</button>`).join("");
  const shown = cfg.paged || cfg.base.includes("alumni") ? st.items : st.items.filter((x) => !st.status || x.status === st.status);
  $("[data-review-list]").innerHTML = shown.length ? shown.map((x) => {
    const r = cfg.row(x);
    const [cls, label] = cfg.labels[x.status] || ["", x.status];
    return `<li><button type="button" class="flex w-full flex-wrap items-center gap-x-4 gap-y-1 px-5 py-3.5 text-left hover:bg-canvas" data-ropen="${esc(x.id)}">
      <span class="min-w-0 flex-1 basis-[14rem]"><span class="block font-semibold"><span class="tag ${cls} mr-2 align-[0.1em]">${label}</span>${esc(r.title)}</span>
      <span class="block truncate text-[0.9375rem] text-ink-2">${esc(r.sub)}</span></span>
      <span class="text-[0.875rem] text-ink-3">${esc(when(r.date))}</span>${icon("chevron-right", "icon-sm text-ink-3")}</button></li>`;
  }).join("") : `<li class="px-5 py-10 text-center text-ink-2">${icon("inbox", "icon mx-auto mb-2 text-ink-3")}${st.q || st.status || st.filter ? "Nothing matches." : "Nothing here yet."}</li>`;
  const pages = cfg.paged ? Math.ceil(st.total / 25) : 1;
  $("[data-review-foot]").innerHTML = `${cfg.email && st.smtp === false ? `<span class="font-semibold text-amber-700">No mail server is set up (SMTP_HOST), so emails are recorded here but not sent.</span>` : `${st.total} in total`}
    ${pages > 1 ? `<span class="ml-auto flex items-center gap-2"><button type="button" class="btn btn-outline btn-sm" data-rpage="-1" ${st.page <= 1 ? "disabled" : ""}>Previous</button><span>Page ${st.page} of ${pages}</span><button type="button" class="btn btn-outline btn-sm" data-rpage="1" ${st.page >= pages ? "disabled" : ""}>Next</button></span>` : ""}`;
}

/* ---------- detail sheet ---------- */

async function open(id) {
  const cfg = VIEWS[st.view];
  const { esc, icon } = ctx;
  let item;
  try { item = await cfg.detail(id); } catch (err) { return ctx.toastError(err); }
  if (!item) return;
  st.current = item;
  const [cls, label] = cfg.labels[item.status] || ["", item.status];
  $("[data-review-sheet-title]").textContent = cfg.row(item).title || "Details";
  const sec = cfg.sections(item).map(([h, rows]) => {
    const filled = rows.filter(([, v]) => v);
    if (!filled.length) return "";
    return `<section class="mt-6"><h3 class="text-[0.8125rem] font-semibold tracking-[0.06em] text-ink-3 uppercase">${esc(h)}</h3><dl class="mt-2 divide-y divide-line-2">${filled.map(([k, v]) =>
      k ? `<div class="grid gap-1 py-2 sm:grid-cols-[11rem_1fr]"><dt class="text-ink-3">${esc(k)}</dt><dd class="break-words">${/^https?:\/\//.test(v) ? `<a class="text-brand-700 hover:underline" href="${esc(v)}" target="_blank" rel="noopener">${esc(v)}</a>` : esc(v)}</dd></div>`
        : `<div class="py-2 whitespace-pre-line text-ink-2">${esc(v)}</div>`).join("")}</dl></section>`;
  }).join("");
  const docs = cfg.docs ? cfg.docs(item) : [];
  const moves = cfg.moves ? cfg.moves(item) : item.moves || [];
  const history = (item.history || []).map((h) => `<li class="py-2"><span class="font-semibold">${esc(cfg.labels[h.status]?.[1] || h.status_label || h.status)}</span> <span class="text-ink-3">· ${esc(when(h.at))}${h.by ? ` · ${esc(h.by)}` : ""}${h.emailed ? " · emailed" : ""}</span>${h.message ? `<p class="text-ink-2">${esc(h.message)}</p>` : ""}</li>`).join("");
  $("[data-review-body]").innerHTML = `
    <p><span class="tag ${cls}">${label}</span></p>
    ${item.message && !cfg.email ? `<p class="mt-3 rounded-sm bg-canvas p-3 text-[0.9375rem]"><span class="font-semibold">Last message to them:</span> ${esc(item.message)}</p>` : ""}
    ${item.review_note ? `<p class="mt-3 rounded-sm bg-canvas p-3 text-[0.9375rem]"><span class="font-semibold">Reason given:</span> ${esc(item.review_note)}</p>` : ""}
    ${docs.length ? `<div class="mt-5 flex flex-wrap gap-2">${docs.map(([l, href]) => `<a class="btn btn-outline btn-sm" href="${esc(href)}" target="_blank" rel="noopener">${icon("file-text")}${esc(l)}</a>`).join("")}</div>` : ""}
    ${sec}
    ${cfg.body ? `<section class="mt-6"><h3 class="text-[0.8125rem] font-semibold tracking-[0.06em] text-ink-3 uppercase">Message</h3><pre class="mt-2 whitespace-pre-wrap rounded-sm bg-canvas p-3 font-sans text-[0.9375rem]">${esc(cfg.body(item))}</pre></section>` : ""}
    ${cfg.email && item.status === "failed" ? `<button type="button" class="btn btn-primary mt-5" data-retry>Send again</button>` : ""}
    ${cfg.extra ? cfg.extra(item) : ""}
    ${history ? `<section class="mt-6"><h3 class="text-[0.8125rem] font-semibold tracking-[0.06em] text-ink-3 uppercase">History</h3><ol class="mt-1 divide-y divide-line-2 text-[0.9375rem]">${history}</ol></section>` : ""}
    ${cfg.note ? `<form class="mt-6" data-note><label class="field-label" for="review-note">Internal note <span class="font-normal text-ink-3">(never shown to the applicant)</span></label><textarea id="review-note" class="field min-h-20 py-2.5" maxlength="4000">${esc(item[cfg.note.field] || "")}</textarea><button class="btn btn-outline btn-sm mt-2" type="submit">Save note</button></form>` : ""}`;
  const action = $("[data-review-action]");
  action.hidden = !moves.length;
  if (moves.length) {
    action.innerHTML = `<div class="grid gap-3 sm:grid-cols-[1fr_auto]">
        <div><label class="field-label" for="review-move">Next step</label><select id="review-move" class="field">${moves.map((m) => `<option value="${m}">${esc(cfg.labels[m]?.[2] || cfg.labels[m]?.[1] || m)}</option>`).join("")}</select></div>
        <label class="flex items-end gap-2 pb-3 text-[0.9375rem] font-semibold"><input type="checkbox" class="h-5 w-5 accent-brand-700" data-notify checked>Email them</label>
      </div>
      <label class="field-label mt-3" for="review-message">Message to include <span class="font-normal text-ink-3" data-move-hint></span></label>
      <textarea id="review-message" class="field min-h-20 py-2.5" maxlength="4000"></textarea>
      <div class="mt-3 flex items-center gap-3"><button type="button" class="btn btn-primary" data-do-move>Update</button><p class="text-[0.9375rem] font-semibold text-om-700" role="alert" data-move-error></p></div>`;
    const hint = () => { $("[data-move-hint]").textContent = cfg.messageHint?.[$("#review-move").value] || "(optional)"; };
    $("#review-move").addEventListener("change", hint);
    hint();
  }
  ctx.drawers.setOpen(document.getElementById("review-sheet"), true);
}

async function doMove() {
  const cfg = VIEWS[st.view];
  const status = $("#review-move").value;
  const btn = $("[data-do-move]");
  btn.disabled = true;
  try {
    const item = await cfg.move(st.current, { status, message: $("#review-message").value.trim(), notify: $("[data-notify]").checked });
    ctx.toast(`${ctx.icon("check")}<span>${ctx.esc(cfg.row(item).title)}: ${ctx.esc(cfg.labels[status][1])}.${$("[data-notify]").checked ? " They've been emailed." : ""}</span>`);
    await load();
    open(item.id);
  } catch (err) {
    $("[data-move-error]").textContent = err.message;
  } finally { btn.disabled = false; }
}

/* ---------- public API ---------- */

export const REVIEW_VIEWS = Object.keys(VIEWS);
export const reviewTitle = (v) => VIEWS[v]?.title;
export const reviewRoles = (v) => VIEWS[v]?.roles || [];

export function showReview(view, arg) {
  const cfg = VIEWS[view];
  Object.assign(st, { view, status: "", q: "", filter: "", page: 1 });
  $("[data-review-heading]").textContent = cfg.title;
  $("[data-review-intro]").textContent = cfg.intro;
  $("[data-review-search]").value = "";
  const csv = $("[data-review-csv]");
  csv.hidden = !cfg.csv;
  const sel = $("[data-review-select]");
  sel.hidden = !cfg.filter;
  if (cfg.filter) {
    sel.innerHTML = `<option value="">${cfg.filter.label}</option>`;
    cfg.filter.load().then((opts) => {
      sel.innerHTML = `<option value="">${cfg.filter.label}</option>${opts.map(([v, l]) => `<option value="${ctx.esc(v)}">${ctx.esc(l)}</option>`).join("")}`;
      if (arg) { sel.value = arg; st.filter = arg; load(); }
    }).catch(() => {});
  }
  const updateCsv = () => {
    if (!cfg.csv) return;
    const p = new URLSearchParams();
    if (st.status) p.set("status", st.status);
    if (st.filter && cfg.filter) p.set(cfg.filter.name, st.filter);
    csv.href = `${cfg.csv}?${p}`;
  };
  st.updateCsv = updateCsv;
  updateCsv();
  $("[data-review-list]").innerHTML = `<li class="px-5 py-10 text-center text-ink-2">Loading…</li>`;
  if (!arg) load();
}

export function initReview(context) {
  ctx = context;
  let t;
  $("[data-review-search]").addEventListener("input", (e) => { clearTimeout(t); t = setTimeout(() => { st.q = e.target.value.trim(); st.page = 1; load(); }, 250); });
  $("[data-review-select]").addEventListener("change", (e) => { st.filter = e.target.value; st.page = 1; st.updateCsv(); load(); });
  document.addEventListener("click", async (e) => {
    const s = e.target.closest("[data-rstatus]");
    if (s) { st.status = s.dataset.rstatus; st.page = 1; st.updateCsv(); const cfg = VIEWS[st.view]; return cfg.paged || cfg.base.includes("alumni") ? load() : render(); }
    const o = e.target.closest("[data-ropen]");
    if (o) return open(o.dataset.ropen);
    const pg = e.target.closest("[data-rpage]");
    if (pg) { st.page += Number(pg.dataset.rpage); return load(); }
    if (e.target.closest("[data-do-move]")) return doMove();
    if (e.target.closest("[data-retry]")) {
      try { await ctx.api(`/notify/messages/${st.current.id}/retry`, { method: "POST" }); ctx.toast(`${ctx.icon("check")}<span>Sent again.</span>`); await load(); open(st.current.id); } catch (err) { ctx.toastError(err); }
    }
  });
  document.addEventListener("change", async (e) => {
    if (!e.target.matches("[data-feature]")) return;
    try {
      const { item } = await ctx.api(`/alumni/review/profiles/${st.current.id}`, { method: "PATCH", json: { featured: e.target.checked } });
      ctx.toast(`${ctx.icon("check")}<span>${ctx.esc(item.full_name)} ${item.featured ? "is featured on the home page" : "is no longer featured"}.</span>`);
      await load();
    } catch (err) { e.target.checked = !e.target.checked; ctx.toastError(err); }
  });
  document.addEventListener("submit", async (e) => {
    if (!e.target.matches("[data-note]")) return;
    e.preventDefault();
    try { await VIEWS[st.view].note.save(st.current, $("#review-note").value); ctx.toast(`${ctx.icon("check")}<span>Note saved.</span>`); } catch (err) { ctx.toastError(err); }
  });
}
