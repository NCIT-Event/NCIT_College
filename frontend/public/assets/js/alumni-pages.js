// Alumni: the public directory, and registering as alumni (profile + verification status).

import { initPhotos } from "./site.js";
import { call, currentUser, errorText, esc, icon, loadPublic, nptDate, signedInBar, signInCard } from "./portal.js";

const $ = (s, root = document) => root.querySelector(s);
const body = $('[data-c="body"]');
const page = document.body.dataset.page;
const params = new URLSearchParams(location.search);

function preview(flag) { if (flag) $('[data-c="preview-banner"]').classList.remove("hidden"); }

export function alumniCard(a) {
  const where = [a.current_role, a.employer].filter(Boolean).join(", ");
  return `<li class="flex gap-4">
    <div class="photo aspect-square w-20 flex-none rounded-sm sm:w-24">${a.photo ? `<img src="${esc(a.photo)}" alt="" loading="lazy">` : `<span class="absolute inset-0 grid place-items-center bg-brand-50 font-serif text-[1.75rem] font-semibold text-brand-700" aria-hidden="true">${esc((a.full_name || "?").split(/\s+/).map((w) => w[0]).slice(0, 2).join(""))}</span>`}</div>
    <div class="min-w-0">
      <p class="font-semibold">${esc(a.full_name)}</p>
      <p class="text-[0.9375rem] text-ink-2">${esc(a.programme)}, ${esc(a.graduation_year)}</p>
      ${where ? `<p class="text-[0.9375rem] text-ink-2">${esc(where)}</p>` : ""}
      <p class="text-[0.875rem] text-ink-3">${esc([a.city, a.country !== "Nepal" ? a.country : ""].filter(Boolean).join(", "))}${a.linkedin_url ? ` · <a class="font-semibold text-brand-700 hover:underline" href="${esc(a.linkedin_url)}" rel="noopener" target="_blank">LinkedIn</a>` : ""}</p>
    </div>
  </li>`;
}

async function directory() {
  const q = params.get("q") || "", programme = params.get("programme") || "", year = params.get("year") || "";
  const pageNo = Math.max(Number(params.get("page") || 1), 1);
  const qs = new URLSearchParams(Object.entries({ q, programme, year, page: pageNo > 1 ? pageNo : "" }).filter(([, v]) => v));
  const { data, preview: isPreview } = await loadPublic("alumni", `directory?${qs}`, "directory");
  preview(isPreview);
  if (!data) { body.innerHTML = `<p class="text-ink-2">The directory couldn't be loaded. Try again in a minute.</p>`; return; }
  const years = Array.from({ length: new Date().getFullYear() - 2004 }, (_, i) => String(new Date().getFullYear() - i));
  const pages = Math.ceil(data.total / data.per_page);
  const link = (p, label) => { const n = new URLSearchParams(qs); n.set("page", p); return `<a class="btn btn-outline btn-sm" href="/alumni?${n}">${label}</a>`; };
  body.innerHTML = `<div class="flex flex-wrap items-end justify-between gap-6">
      <p class="max-w-[60ch] text-ink-2">${data.verified_total ? `${data.verified_total} verified alumni so far. ` : ""}Only verified alumni who chose to be listed appear here; contact details are never shown.</p>
      <a class="btn btn-primary" href="/alumni/join">${icon("user-plus")}Register as alumni</a>
    </div>
    <form class="mt-8 grid gap-3 rounded-sm border border-line bg-canvas p-4 sm:grid-cols-[1fr_auto_auto_auto]" role="search" method="get" action="/alumni">
      <div><label class="sr-only" for="a-q">Search alumni</label><input id="a-q" name="q" class="field" type="search" placeholder="Name, organisation, role or city" value="${esc(q)}"></div>
      <div><label class="sr-only" for="a-programme">Programme</label><select id="a-programme" name="programme" class="field"><option value="">All programmes</option>${(data.programmes || []).map((p) => `<option ${p === programme ? "selected" : ""}>${esc(p)}</option>`).join("")}</select></div>
      <div><label class="sr-only" for="a-year">Year</label><select id="a-year" name="year" class="field"><option value="">Any year</option>${years.map((y) => `<option ${y === year ? "selected" : ""}>${y}</option>`).join("")}</select></div>
      <button class="btn btn-primary" type="submit">${icon("search")}Search</button>
    </form>
    ${data.items.length ? `<ul class="mt-10 grid gap-x-8 gap-y-8 sm:grid-cols-2 lg:grid-cols-3">${data.items.map(alumniCard).join("")}</ul>`
      : `<p class="mt-10 text-ink-2">${q || programme || year ? "No alumni match that search." : "No alumni are listed yet."}</p>`}
    ${pages > 1 ? `<nav class="mt-10 flex items-center justify-between" aria-label="Pages"><span class="text-ink-2">Page ${data.page} of ${pages}</span><span class="flex gap-2">${data.page > 1 ? link(data.page - 1, "Previous") : ""}${data.page < pages ? link(data.page + 1, "Next") : ""}</span></nav>` : ""}`;
  initPhotos(body);
}

const STATUS = { draft: ["tag-om", "Not sent yet"], pending: ["tag-amber", "Waiting for verification"], verified: ["tag-leaf", "Verified"], rejected: ["", "Not verified"] };

async function join() {
  body.innerHTML = `<p class="text-ink-2">Loading…</p>`;
  const { user, offline } = await currentUser();
  if (offline) { preview(true); body.innerHTML = `<p class="text-ink-2">Registering needs the alumni service, which isn't running in this preview.</p>`; return; }
  if (!user) {
    body.innerHTML = `<div class="max-w-[44rem]" data-signin></div>`;
    signInCard($("[data-signin]"), { purpose: "alumni", title: "Sign in to register",
      lead: "Use an email address you'll keep. We'll send a one-time code; you'll use the same address to update your profile later.",
      onDone: () => join() });
    return;
  }
  const res = await call("alumni/me/profile");
  profileForm(user, res.body?.profile || { show_in_directory: true, country: "Nepal", status: "draft" });
}

function profileForm(user, p) {
  const [cls, label] = STATUS[p.status] || STATUS.draft;
  const f = (name, labelText, opts = {}) => `<div class="${opts.wide ? "sm:col-span-2" : ""}"><label class="field-label" for="p-${name}">${labelText}${opts.optional ? ` <span class="font-normal text-ink-3">(optional)</span>` : ""}</label>
    <input id="p-${name}" name="${name}" class="field" type="${opts.type || "text"}" value="${esc(p[name] || "")}" ${opts.attrs || ""}>${opts.hint ? `<p class="mt-1.5 text-[0.875rem] text-ink-3">${opts.hint}</p>` : ""}</div>`;
  body.innerHTML = `${signedInBar(user)}
    <div class="mt-6 flex flex-wrap items-center gap-3"><span class="tag ${cls}">${label}</span>${p.verified_at ? `<span class="text-[0.9375rem] text-ink-3">since ${esc(nptDate(p.verified_at))}</span>` : ""}</div>
    ${p.status === "rejected" && p.review_note ? `<div class="mt-4 max-w-[46rem] rounded-sm border-l-4 border-amber-700 bg-amber-50 p-4"><p class="font-semibold text-amber-700">The alumni office couldn't verify your details</p><p class="mt-1">${esc(p.review_note)}</p><p class="mt-2 text-[0.9375rem] text-ink-2">Correct them below and send again.</p></div>` : ""}
    ${p.status === "pending" ? `<p class="mt-3 max-w-[60ch] text-ink-2">The alumni office is checking your details against college records. We'll email you when it's done. You can still update your profile meanwhile.</p>` : ""}
    <form class="mt-8 max-w-[46rem] space-y-10" data-profile novalidate>
      <fieldset><legend class="font-serif text-h3 font-semibold">Your time at NCIT</legend>
        <p class="mt-1 text-[0.9375rem] text-ink-3">The alumni office checks these against college records. Changing them later means checking again.</p>
        <div class="mt-4 grid gap-5 sm:grid-cols-2">
          ${f("full_name", "Full name (as on your degree)", { wide: true, attrs: 'maxlength="160" autocomplete="name"' })}
          ${f("programme", "Programme", { attrs: 'maxlength="120" list="programmes" placeholder="e.g. BE Computer Engineering"' })}
          ${f("graduation_year", "Year of graduation", { attrs: 'inputmode="numeric" maxlength="4" placeholder="2015"' })}
          ${f("registration_no", "Pokhara University registration number", { attrs: 'maxlength="40"', hint: "On your transcript or PU registration card." })}
          ${f("phone", "Phone", { type: "tel", optional: true, attrs: 'maxlength="30" autocomplete="tel"', hint: "Only the alumni office sees this." })}
        </div>
        <datalist id="programmes">${["BE Computer Engineering", "BE Information Technology", "BE Software Engineering", "BE Information & Communication Engineering", "BE Civil Engineering", "Bachelor of Architecture", "Bachelor of Computer Applications", "Bachelor of Business Administration", "ME Computer Engineering", "Master of Computer Information Systems", "MSc Computer Science"].map((x) => `<option value="${esc(x)}">`).join("")}</datalist>
      </fieldset>
      <fieldset><legend class="font-serif text-h3 font-semibold">What you do now</legend>
        <div class="mt-4 grid gap-5 sm:grid-cols-2">
          ${f("current_role", "Role", { optional: true, attrs: 'maxlength="120" placeholder="e.g. Software engineer"' })}
          ${f("employer", "Organisation", { optional: true, attrs: 'maxlength="120"' })}
          ${f("city", "City", { optional: true, attrs: 'maxlength="80"' })}
          ${f("country", "Country", { optional: true, attrs: 'maxlength="80"' })}
          ${f("linkedin_url", "LinkedIn profile", { optional: true, wide: true, type: "url", attrs: 'maxlength="300" placeholder="https://www.linkedin.com/in/…"' })}
          ${f("bio", "A line about you", { optional: true, wide: true, attrs: 'maxlength="400"' })}
        </div>
        <div class="mt-5 flex items-center gap-4" data-photo>
          <div class="photo h-20 w-20 flex-none rounded-sm" data-photo-preview>${p.photo ? `<img src="${esc(p.photo)}" alt="">` : ""}</div>
          <label class="btn btn-outline btn-sm cursor-pointer focus-within:outline-2 focus-within:outline-brand-600">${icon("camera")}<span data-photo-label>${p.photo ? "Replace photo" : "Add a photo"}</span><input type="file" accept="image/jpeg,image/png,image/webp" class="sr-only" data-photo-input></label>
          <span class="text-[0.875rem] text-ink-3">Optional. Shown in the directory.</span>
        </div>
        <label class="mt-6 flex cursor-pointer items-start gap-3"><input type="checkbox" name="show_in_directory" class="mt-1 h-5 w-5 accent-brand-700" ${p.show_in_directory ? "checked" : ""}><span><span class="font-semibold">Show me in the alumni directory</span><span class="block text-[0.9375rem] text-ink-2">Your name, programme, year, role, organisation, city, LinkedIn and photo. Never your email or phone.</span></span></label>
      </fieldset>
      <div class="flex flex-wrap items-center gap-3 border-t border-line pt-6">
        <button type="submit" class="btn btn-primary">${p.status === "draft" || p.status === "rejected" ? "Send for verification" : "Save changes"}</button>
        <p class="text-[0.9375rem] text-ink-2" role="status" data-profile-status></p>
      </div>
      <p class="text-[0.9375rem] font-semibold text-om-700" role="alert" data-profile-error></p>
    </form>`;
  initPhotos(body);
  const form = $("[data-profile]");
  const err = $("[data-profile-error]"), status = $("[data-profile-status]");
  $("[data-photo-input]").addEventListener("change", async (e) => {
    const file = e.target.files[0];
    e.target.value = "";
    if (!file) return;
    $("[data-photo-label]").textContent = "Uploading…";
    const fd = new FormData();
    fd.append("file", file);
    const res = await call("alumni/me/profile/photo", { method: "POST", form: fd });
    if (!res.ok) { err.textContent = errorText(res); $("[data-photo-label]").textContent = "Add a photo"; return; }
    p = res.body.profile;
    $("[data-photo-preview]").innerHTML = `<img src="${esc(p.photo)}" alt="">`;
    $("[data-photo-label]").textContent = "Replace photo";
  });
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    err.textContent = "";
    const data = Object.fromEntries([...form.querySelectorAll("input[name]")].map((el) => [el.name, el.type === "checkbox" ? el.checked : el.value.trim()]));
    status.textContent = "Saving…";
    let res = await call("alumni/me/profile", { method: "PUT", json: data });
    if (res.ok && ["draft", "rejected"].includes(res.body.profile.status)) res = await call("alumni/me/profile/submit", { method: "POST" });
    status.textContent = "";
    if (!res.ok) { err.textContent = errorText(res); return; }
    const before = p.status;
    profileForm(user, res.body.profile);
    $("[data-profile-status]").textContent = res.body.profile.status === "pending" && before !== "pending"
      ? "Sent. The alumni office will check your details and email you." : "Saved.";
  });
}

if (page === "alumni") directory();
if (page === "alumni-join") join();
