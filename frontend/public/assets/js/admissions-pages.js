// Admissions (programmes open for applications) and Apply online (the applicant portal).

import { call, currentUser, errorText, esc, icon, loadPublic, nptDate, signedInBar, signInCard } from "./portal.js";
import { paragraphs } from "./content-shared.js";

const $ = (s, root = document) => root.querySelector(s);
const body = $('[data-c="body"]');
const page = document.body.dataset.page;

const STATUS = {
  draft: ["tag-om", "Draft: not sent yet"], submitted: ["", "Submitted"], under_review: ["", "Under review"],
  documents_requested: ["tag-amber", "More documents needed"], accepted: ["tag-leaf", "Accepted"],
  waitlisted: ["tag-amber", "Waiting list"], rejected: ["", "Not accepted"], withdrawn: ["", "Withdrawn"],
};
const tag = (s) => { const [cls, label] = STATUS[s] || ["", s]; return `<span class="tag ${cls}">${label}</span>`; };

function preview(flag) { if (flag) $('[data-c="preview-banner"]').classList.remove("hidden"); }

/* ---------- /admissions ---------- */

async function admissions() {
  const { data, preview: isPreview } = await loadPublic("admissions", "intakes", "intakes");
  preview(isPreview);
  const intakes = data?.items || [];
  if (!intakes.length) {
    body.innerHTML = `<p class="max-w-[60ch] text-[1.125rem] text-ink-2">No intake is open right now. The next one will be announced on the <a class="font-semibold text-brand-700 hover:underline" href="/notices?category=admission">admission notices</a> page.</p>`;
    return;
  }
  body.innerHTML = intakes.map((x) => `
    <section class="grid gap-10 lg:grid-cols-[1fr_22rem] lg:gap-16" aria-labelledby="intake-${esc(x.id)}">
      <div class="min-w-0">
        <h2 id="intake-${esc(x.id)}" class="font-serif text-h2 font-semibold">${esc(x.name)}</h2>
        <div class="mt-4 max-w-[66ch] space-y-4 text-[1.125rem] text-ink-2">${paragraphs(x.intro)}</div>
        <h3 id="programmes" class="mt-12 scroll-mt-32 font-serif text-h3 font-semibold">Programmes</h3>
        <ul class="mt-4 divided border-y border-line">${x.offerings.map((o) => `
          <li class="py-5">
            <div class="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
              <h4 class="text-[1.1875rem] font-semibold">${esc(o.programme)}</h4>
              ${o.seats ? `<p class="text-[0.9375rem] text-ink-3">${o.seats} seats</p>` : ""}
            </div>
            ${o.eligibility ? `<p class="mt-1 max-w-[70ch] text-ink-2"><span class="font-semibold text-ink">Who can apply:</span> ${esc(o.eligibility)}</p>` : ""}
            ${o.fee_note ? `<p class="mt-1 max-w-[70ch] text-[0.9375rem] text-ink-3">${esc(o.fee_note)}</p>` : ""}
          </li>`).join("")}</ul>
      </div>
      <aside class="lg:sticky lg:top-28 lg:self-start" aria-label="Dates and how to apply">
        <div id="dates" class="scroll-mt-32 rounded-sm border border-line bg-white p-6">
          <p><span class="tag ${x.status === "open" ? "tag-leaf" : "tag-amber"}">${x.status === "open" ? "Open now" : "Opens soon"}</span></p>
          <dl class="mt-4 divided">
            <div class="flex justify-between gap-4 py-3"><dt class="text-ink-3">Applications open</dt><dd class="font-semibold">${esc(nptDate(x.opens_at))}</dd></div>
            <div class="flex justify-between gap-4 py-3"><dt class="text-ink-3">Applications close</dt><dd class="font-semibold">${esc(nptDate(x.closes_at, true))}</dd></div>
          </dl>
          ${x.status === "open" ? `<a class="btn btn-apply mt-5 w-full" href="/apply">Start your application</a>` : ""}
          <a class="btn btn-outline mt-3 w-full" href="/apply">Track an application</a>
          <ol class="mt-6 space-y-3 border-t border-line pt-5 text-[0.9375rem] text-ink-2">
            <li><strong class="text-ink">1.</strong> Sign in with your email: we send you a one-time code.</li>
            <li><strong class="text-ink">2.</strong> Fill in the form and upload your photo and transcript. You can save and come back.</li>
            <li><strong class="text-ink">3.</strong> Send it, and follow its status here. We email you at every step.</li>
          </ol>
        </div>
      </aside>
    </section>`).join(`<hr class="my-16 border-line">`);
}

/* ---------- /apply ---------- */

const st = { user: null, intakes: [], apps: [] };

async function applyPage() {
  body.innerHTML = `<p class="text-ink-2">Loading…</p>`;
  const [{ user, offline }, pub] = await Promise.all([currentUser(), loadPublic("admissions", "intakes", "intakes")]);
  st.intakes = pub.data?.items || [];
  if (offline || pub.preview) {
    preview(true);
    body.innerHTML = `<p class="max-w-[60ch] text-ink-2">Online applications need the admissions service, which isn't running in this preview. The programmes on offer are listed on the <a class="font-semibold text-brand-700 hover:underline" href="/admissions">Admissions</a> page.</p>`;
    return;
  }
  st.user = user;
  if (!user) return showSignIn();
  await loadMine();
  route();
}

function showSignIn() {
  body.innerHTML = `<div class="grid gap-12 lg:grid-cols-[1fr_24rem] lg:gap-16"><div data-signin class="min-w-0"></div>
    <aside class="text-ink-2"><h2 class="font-semibold text-ink">Before you start</h2>
      <ul class="mt-3 list-disc space-y-2 pl-5"><li>Your +2 (or equivalent) transcript as a PDF</li><li>A passport-size photo (JPEG or PNG)</li><li>Citizenship or passport as a PDF (you can add it later)</li><li>Your parent or guardian's contact details</li></ul>
      <p class="mt-4">You can save your application and finish it later, until the closing date.</p></aside></div>`;
  signInCard($("[data-signin]"), {
    purpose: "applicant", title: "Sign in to apply or track your application",
    lead: "Use the email address you want us to contact you on. You'll use the same address to come back later.",
    onDone: async (user) => { st.user = user; await loadMine(); route(); },
  });
}

async function loadMine() {
  const res = await call("admissions/me/applications");
  st.apps = res.ok ? res.body.items : [];
}

function route() {
  const id = location.hash.match(/^#app-(.+)$/)?.[1];
  const app = st.apps.find((a) => a.id === id);
  app ? showApplication(app) : showList();
  window.scrollTo({ top: 0 });
}
window.addEventListener("hashchange", () => { if (st.user) route(); });

function showList() {
  const open = st.intakes.filter((x) => x.status === "open" && !st.apps.some((a) => a.intake.id === x.id && a.status !== "withdrawn"));
  body.innerHTML = `${signedInBar(st.user)}
    <h2 class="mt-8 font-serif text-h3 font-semibold">Your applications</h2>
    ${st.apps.length ? `<ul class="mt-4 divided border-y border-line">${st.apps.map((a) => `
      <li class="group relative flex flex-wrap items-center gap-x-6 gap-y-2 py-5">
        <div class="min-w-0 flex-1">
          <p class="flex flex-wrap items-center gap-2 text-[0.875rem] text-ink-3">${tag(a.status)}${a.reference ? `<span>${esc(a.reference)}</span>` : ""}<span>${esc(a.intake.name)}</span></p>
          <h3 class="mt-1.5 text-[1.1875rem] font-semibold"><a class="after:absolute after:inset-0 group-hover:text-brand-700" href="#app-${esc(a.id)}">${esc(a.offering.programme)}</a></h3>
          ${a.status === "draft" ? `<p class="mt-1 text-[0.9375rem] text-ink-2">Not sent yet. Applications close ${esc(nptDate(a.intake.closes_at, true))}.</p>` : a.message ? `<p class="mt-1 text-[0.9375rem] text-ink-2">${esc(a.message)}</p>` : ""}
        </div>
        <span class="link-arrow">${a.editable ? "Continue" : "View"} ${icon("arrow-right")}</span>
      </li>`).join("")}</ul>` : `<p class="mt-3 text-ink-2">You haven't started an application yet.</p>`}
    ${open.length ? `<section class="mt-12 rounded-sm border border-line bg-white p-6 sm:p-8" aria-labelledby="start-title">
      <h2 id="start-title" class="font-serif text-h3 font-semibold">Start a new application</h2>
      <form class="mt-4 flex flex-col gap-3 sm:flex-row sm:items-end" data-start>
        <div class="min-w-0 flex-1"><label class="field-label" for="start-offering">Programme</label>
          <select id="start-offering" class="field" required>${open.map((x) => `<optgroup label="${esc(x.name)}">${x.offerings.map((o) => `<option value="${esc(o.id)}">${esc(o.programme)}</option>`).join("")}</optgroup>`).join("")}</select></div>
        <button class="btn btn-apply" type="submit">Start</button>
      </form>
      <p class="mt-3 text-[0.9375rem] font-semibold text-om-700" role="alert" data-start-error></p>
    </section>` : st.apps.length ? "" : `<p class="mt-8 text-ink-2">No intake is open right now. See <a class="font-semibold text-brand-700 hover:underline" href="/admissions">Admissions</a> for dates.</p>`}`;
  $("[data-start]")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const res = await call("admissions/me/applications", { method: "POST", json: { offering_id: $("#start-offering").value } });
    if (!res.ok) { $("[data-start-error]").textContent = errorText(res); return; }
    await loadMine();
    location.hash = `app-${res.body.item.id}`;
  });
}

const DOCS = { photo: ["Passport-size photo", "JPEG or PNG, up to 8 MB", "image/jpeg,image/png,image/webp", true],
  transcript: ["+2 transcript (or equivalent)", "PDF, up to 10 MB", "application/pdf", true],
  citizenship: ["Citizenship or passport", "PDF, up to 10 MB. Optional now, may be asked for later.", "application/pdf", false] };

const input = (a, name, label, opts = {}) => `<div class="${opts.wide ? "sm:col-span-2" : ""}">
  <label class="field-label" for="f-${name}">${label}${opts.optional ? ` <span class="font-normal text-ink-3">(optional)</span>` : ""}</label>
  <input id="f-${name}" name="${name}" class="field" type="${opts.type || "text"}" value="${esc(a[name] || "")}" ${opts.attrs || ""}>
  ${opts.hint ? `<p class="mt-1.5 text-[0.875rem] text-ink-3">${opts.hint}</p>` : ""}</div>`;

async function showApplication(a) {
  if (!a.editable) return showReadOnly(a);
  const res = await call(`admissions/me/intakes/${a.intake.id}`);
  const programmes = res.ok ? res.body.items : [a.offering];
  const opt = (sel) => programmes.map((p) => `<option value="${esc(p.id)}" ${p.id === sel ? "selected" : ""}>${esc(p.programme)}</option>`).join("");
  body.innerHTML = `${signedInBar(st.user)}
    <p class="mt-4"><a class="link-arrow" href="#">${icon("chevron-left")} Your applications</a></p>
    <div class="mt-6 flex flex-wrap items-center gap-3">${tag(a.status)}<span class="text-ink-3">${esc(a.intake.name)} · closes ${esc(nptDate(a.intake.closes_at, true))}</span></div>
    ${a.status === "documents_requested" ? `<div class="mt-4 rounded-sm border-l-4 border-amber-700 bg-amber-50 p-4"><p class="font-semibold text-amber-700">The admissions office needs more from you</p><p class="mt-1 text-ink">${esc(a.message)}</p><p class="mt-2 text-[0.9375rem] text-ink-2">Make the changes below, then press <strong>Send application</strong> again.</p></div>` : ""}
    <form class="mt-8 space-y-12" data-app novalidate>
      <fieldset><legend class="font-serif text-h3 font-semibold">1. Programme</legend>
        <div class="mt-4 grid gap-5 sm:grid-cols-2">
          <div><label class="field-label" for="f-offering_id">First choice</label><select id="f-offering_id" name="offering_id" class="field">${opt(a.offering.id)}</select></div>
          <div><label class="field-label" for="f-second_choice_id">Second choice <span class="font-normal text-ink-3">(optional)</span></label><select id="f-second_choice_id" name="second_choice_id" class="field"><option value="">None</option>${opt(a.second_choice?.id)}</select></div>
        </div></fieldset>
      <fieldset><legend class="font-serif text-h3 font-semibold">2. About you</legend>
        <div class="mt-4 grid gap-5 sm:grid-cols-2">
          ${input(a, "full_name", "Full name (as on your certificates)", { wide: true, attrs: 'autocomplete="name" maxlength="160"' })}
          ${input(a, "date_of_birth", "Date of birth (AD)", { type: "date" })}
          <div><label class="field-label" for="f-gender">Gender <span class="font-normal text-ink-3">(optional)</span></label><select id="f-gender" name="gender" class="field">${[["", "Choose"], ["female", "Female"], ["male", "Male"], ["other", "Other"], ["prefer_not", "Prefer not to say"]].map(([v, l]) => `<option value="${v}" ${a.gender === v ? "selected" : ""}>${l}</option>`).join("")}</select></div>
          ${input(a, "phone", "Mobile number", { type: "tel", attrs: 'autocomplete="tel" inputmode="tel" maxlength="30"' })}
          ${input(a, "address", "Permanent address", { attrs: 'autocomplete="street-address" maxlength="300"' })}
          ${input(a, "guardian_name", "Parent or guardian's name", { attrs: 'maxlength="160"' })}
          ${input(a, "guardian_phone", "Parent or guardian's phone", { type: "tel", optional: true, attrs: 'inputmode="tel" maxlength="30"' })}
        </div></fieldset>
      <fieldset><legend class="font-serif text-h3 font-semibold">3. Previous study</legend>
        <div class="mt-4 grid gap-5 sm:grid-cols-2">
          ${input(a, "school", "+2 school or college", { wide: true, attrs: 'maxlength="200"' })}
          ${input(a, "board", "Board", { hint: "e.g. NEB, A-Level", attrs: 'maxlength="80"' })}
          ${input(a, "passed_year", "Year passed", { attrs: 'inputmode="numeric" maxlength="4" placeholder="2025"' })}
          ${input(a, "grade", "GPA or percentage", { hint: "As written on your transcript, e.g. 3.45 or 78%", attrs: 'maxlength="20"' })}
          ${input(a, "entrance_score", "Entrance test score", { optional: true, attrs: 'maxlength="20"' })}
        </div></fieldset>
      <fieldset><legend class="font-serif text-h3 font-semibold">4. Documents</legend>
        <ul class="mt-4 divided border-y border-line">${Object.entries(DOCS).map(([k, [label, hint, accept, req]]) => `
          <li class="flex flex-wrap items-center gap-x-6 gap-y-2 py-4" data-doc="${k}">
            <div class="min-w-0 flex-1"><p class="font-semibold">${label}${req ? "" : ` <span class="font-normal text-ink-3">(optional)</span>`}</p><p class="text-[0.875rem] text-ink-3">${hint}</p></div>
            <span class="inline-flex items-center gap-1.5 font-semibold text-leaf-700" ${a.documents[k] ? "" : "hidden"} data-doc-ok>${icon("check")}Uploaded · <a class="text-brand-700 hover:underline" href="/api/v1/admissions/me/applications/${esc(a.id)}/documents/${k}" target="_blank" rel="noopener">View</a></span>
            <label class="btn btn-outline btn-sm cursor-pointer focus-within:outline-2 focus-within:outline-brand-600">${icon("download")}<span data-doc-label>${a.documents[k] ? "Replace" : "Upload"}</span><input type="file" class="sr-only" accept="${accept}" data-doc-input></label>
          </li>`).join("")}</ul></fieldset>
      <div class="sticky bottom-0 -mx-4 flex flex-wrap items-center gap-3 border-t border-line bg-white/95 px-4 py-4 backdrop-blur sm:mx-0 sm:px-0">
        <button type="button" class="btn btn-outline" data-save>Save draft</button>
        <button type="submit" class="btn btn-apply">Send application</button>
        <p class="text-[0.9375rem] text-ink-2" role="status" data-app-status></p>
      </div>
      <p class="text-[0.9375rem] font-semibold text-om-700" role="alert" data-app-error></p>
    </form>
    ${a.status === "draft" ? `<p class="mt-6"><button type="button" class="text-[0.9375rem] font-semibold text-om-700 hover:underline" data-withdraw>Discard this draft</button></p>` : ""}`;
  const form = $("[data-app]");
  const err = $("[data-app-error]"), status = $("[data-app-status]");
  const values = () => Object.fromEntries([...form.querySelectorAll("input[name], select[name]")].map((el) => [el.name, el.value.trim()]));
  async function save() {
    err.textContent = "";
    status.textContent = "Saving…";
    const res = await call(`admissions/me/applications/${a.id}`, { method: "PATCH", json: values() });
    status.textContent = res.ok ? `Saved ${nptDate(new Date().toISOString(), true).split(", ")[1]}` : "";
    if (!res.ok) err.textContent = errorText(res);
    return res.ok;
  }
  $("[data-save]").addEventListener("click", save);
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!(await save())) return;
    status.textContent = "Sending…";
    const res = await call(`admissions/me/applications/${a.id}/submit`, { method: "POST" });
    status.textContent = "";
    if (!res.ok) { err.textContent = errorText(res); return; }
    await loadMine();
    showReadOnly(res.body.item, true);
  });
  form.querySelectorAll("[data-doc]").forEach((row) => {
    row.querySelector("[data-doc-input]").addEventListener("change", async (e) => {
      const file = e.target.files[0];
      e.target.value = "";
      if (!file) return;
      const label = row.querySelector("[data-doc-label]");
      label.textContent = "Uploading…";
      const fd = new FormData();
      fd.append("file", file);
      const res = await call(`admissions/me/applications/${a.id}/documents/${row.dataset.doc}`, { method: "POST", form: fd });
      label.textContent = res.ok || a.documents[row.dataset.doc] ? "Replace" : "Upload";
      if (!res.ok) { err.textContent = errorText(res); return; }
      a.documents = res.body.item.documents;
      row.querySelector("[data-doc-ok]").hidden = false;
    });
  });
  $("[data-withdraw]")?.addEventListener("click", async (e) => {
    if (e.target.dataset.armed !== "1") { e.target.dataset.armed = "1"; e.target.textContent = "Click again to discard the draft"; return; }
    await call(`admissions/me/applications/${a.id}/withdraw`, { method: "POST" });
    await loadMine();
    location.hash = "";
  });
}

function showReadOnly(a, justSent = false) {
  const row = (label, value) => value ? `<div class="grid gap-1 py-3 sm:grid-cols-[14rem_1fr]"><dt class="text-ink-3">${label}</dt><dd class="font-semibold">${esc(value)}</dd></div>` : "";
  const canWithdraw = !["accepted", "rejected", "withdrawn"].includes(a.status);
  body.innerHTML = `${signedInBar(st.user)}
    <p class="mt-4"><a class="link-arrow" href="#">${icon("chevron-left")} Your applications</a></p>
    ${justSent ? `<div class="mt-6 rounded-sm border-l-4 border-leaf-700 bg-leaf-50 p-4" role="status"><p class="font-semibold text-leaf-700">${icon("check", "icon mr-1 inline")}Application sent</p><p class="mt-1">Your reference is <strong>${esc(a.reference)}</strong>. We've emailed you a copy, and we'll email you when anything changes.</p></div>` : ""}
    <div class="mt-8 grid gap-12 lg:grid-cols-[1fr_22rem] lg:gap-16">
      <div class="min-w-0">
        <p class="flex flex-wrap items-center gap-3">${tag(a.status)}<span class="text-ink-3">${esc(a.reference || "")}</span></p>
        <h2 class="mt-3 font-serif text-h2 font-semibold">${esc(a.offering.programme)}</h2>
        <p class="text-ink-2">${esc(a.intake.name)}${a.second_choice ? ` · second choice: ${esc(a.second_choice.programme)}` : ""}</p>
        ${a.message ? `<div class="mt-6 rounded-sm bg-canvas p-4"><p class="text-[0.875rem] font-semibold text-ink-3 uppercase">Message from the admissions office</p><p class="mt-1 text-ink">${esc(a.message)}</p></div>` : ""}
        <h3 class="mt-10 font-semibold">Your details</h3>
        <dl class="mt-2 divided border-y border-line">${row("Full name", a.full_name)}${row("Date of birth", a.date_of_birth)}${row("Mobile", a.phone)}${row("Address", a.address)}${row("Parent or guardian", [a.guardian_name, a.guardian_phone].filter(Boolean).join(" · "))}${row("School", a.school)}${row("Board and year", [a.board, a.passed_year].filter(Boolean).join(", "))}${row("GPA or percentage", a.grade)}${row("Entrance score", a.entrance_score)}${row("Documents", Object.entries(a.documents).filter(([, v]) => v).map(([k]) => DOCS[k][0]).join(", "))}</dl>
        ${canWithdraw ? `<p class="mt-8"><button type="button" class="text-[0.9375rem] font-semibold text-om-700 hover:underline" data-withdraw>Withdraw this application</button></p>` : ""}
      </div>
      <aside aria-label="Progress"><h3 class="font-semibold">Progress</h3>
        <ol class="mt-4 space-y-5 border-l-2 border-line pl-5">${a.history.map((h) => `<li class="relative"><span class="absolute top-1.5 -left-[1.6rem] h-3 w-3 rounded-full bg-brand-700"></span>
          <p class="font-semibold">${esc(h.status_label)}</p><p class="text-[0.875rem] text-ink-3">${esc(nptDate(h.at, true))}</p>${h.message ? `<p class="mt-1 text-[0.9375rem] text-ink-2">${esc(h.message)}</p>` : ""}</li>`).join("")}</ol>
      </aside>
    </div>`;
  $("[data-withdraw]")?.addEventListener("click", async (e) => {
    if (e.target.dataset.armed !== "1") { e.target.dataset.armed = "1"; e.target.textContent = "Click again to withdraw. This can't be undone by you."; return; }
    const res = await call(`admissions/me/applications/${a.id}/withdraw`, { method: "POST" });
    if (res.ok) { await loadMine(); showReadOnly(res.body.item); }
  });
}

if (page === "admissions") admissions();
if (page === "apply") applyPage();
