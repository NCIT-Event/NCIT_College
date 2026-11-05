// Careers: the vacancy list and a vacancy page with the application form.

import { call, currentUser, errorText, esc, icon, loadPublic, nptDate, signedInBar, signInCard } from "./portal.js";
import { paragraphs } from "./content-shared.js";

const $ = (s, root = document) => root.querySelector(s);
const body = $('[data-c="body"]');
const page = document.body.dataset.page;
const KIND = { faculty: "Faculty", staff: "Staff" };
const EMPLOYMENT = { full_time: "Full time", part_time: "Part time", contract: "Contract" };
const STATUS = { submitted: ["", "Received"], shortlisted: ["tag-leaf", "Shortlisted"], interview: ["tag-leaf", "Interview"],
  offered: ["tag-leaf", "Offered"], rejected: ["", "Not taken forward"], withdrawn: ["", "Withdrawn"] };

function preview(flag) { if (flag) $('[data-c="preview-banner"]').classList.remove("hidden"); }
const meta = (j) => [KIND[j.kind], EMPLOYMENT[j.employment], j.positions > 1 ? `${j.positions} positions` : "", j.department].filter(Boolean).map(esc).join(" · ");

async function careers() {
  const { data, preview: isPreview } = await loadPublic("careers", "jobs", "jobs");
  preview(isPreview);
  const jobs = Array.isArray(data) ? data : data?.items || [];
  body.innerHTML = jobs.length ? `<ul class="divided border-y border-line">${jobs.map((j) => `
    <li class="group relative flex flex-wrap items-center gap-x-8 gap-y-2 py-6">
      <div class="min-w-0 flex-1 basis-[20rem]">
        <p class="text-[0.875rem] text-ink-3">${meta(j)}</p>
        <h2 class="mt-1 font-serif text-[1.5rem] leading-snug font-semibold"><a class="after:absolute after:inset-0 group-hover:text-brand-700" href="/careers/${esc(j.slug)}">${esc(j.title)}</a></h2>
        ${j.summary ? `<p class="mt-1 max-w-[70ch] text-ink-2">${esc(j.summary)}</p>` : ""}
      </div>
      <p class="text-[0.9375rem] text-ink-2">Apply by <strong class="font-semibold text-ink">${esc(nptDate(j.closes_at))}</strong></p>
    </li>`).join("")}</ul>` : `<p class="max-w-[60ch] text-[1.125rem] text-ink-2">There are no open positions right now. Vacancies are also announced on the <a class="font-semibold text-brand-700 hover:underline" href="/notices">notices</a> page.</p>`;
}

async function jobPage(slug) {
  const { data, preview: isPreview } = await loadPublic("careers", `jobs/${encodeURIComponent(slug)}`, "jobs");
  preview(isPreview);
  const j = isPreview ? (data || []).find((x) => x.slug === slug) : data?.job;
  if (!j) {
    $('[data-c="title"]').textContent = "Vacancy not found";
    $('[data-c="lead"]').textContent = "It may have closed or been removed.";
    body.innerHTML = `<a class="btn btn-primary" href="/careers">All vacancies</a>`;
    return;
  }
  document.title = `${j.title} · Careers at NCIT`;
  $('[data-c="crumbs"]').insertAdjacentHTML("afterend", `<li aria-hidden="true"><svg class="icon-sm"><use href="/assets/img/icons.svg#i-chevron-right"/></svg></li><li><span aria-current="page" class="text-ink-2">${esc(j.title)}</span></li>`);
  $('[data-c="title"]').textContent = j.title;
  $('[data-c="lead"]').innerHTML = meta(j);
  const open = j.status === "open";
  body.innerHTML = `<div class="grid gap-12 lg:grid-cols-[1fr_26rem] lg:gap-16">
    <article class="min-w-0 max-w-[46rem]">
      ${j.summary ? `<p class="font-serif text-[1.375rem] leading-snug text-ink">${esc(j.summary)}</p>` : ""}
      ${j.description ? `<h2 class="mt-10 font-serif text-h3 font-semibold">About the role</h2><div class="mt-3 space-y-4 text-[1.0625rem] leading-relaxed text-ink-2">${paragraphs(j.description)}</div>` : ""}
      ${j.requirements ? `<h2 class="mt-10 font-serif text-h3 font-semibold">What we're looking for</h2><ul class="mt-3 list-disc space-y-2 pl-5 text-[1.0625rem] text-ink-2">${j.requirements.split(/\n+/).filter((l) => l.trim()).map((l) => `<li>${esc(l.trim())}</li>`).join("")}</ul>` : ""}
      ${j.attachment ? `<p class="mt-8"><a class="btn btn-outline" href="${esc(j.attachment)}">${icon("download")}Full job description (PDF)</a></p>` : ""}
      <p class="mt-12 border-t border-line pt-6"><a class="link-arrow" href="/careers">${icon("chevron-left")} All vacancies</a></p>
    </article>
    <aside class="lg:sticky lg:top-28 lg:self-start" aria-label="Apply">
      <div class="rounded-sm border border-line bg-white p-6">
        <p class="text-ink-2">${open ? "Apply by" : "Applications closed"} <strong class="font-semibold text-ink">${esc(nptDate(j.closes_at, true))}</strong></p>
        <div class="mt-4 border-t border-line pt-5" data-apply aria-live="polite">${isPreview ? `<p class="text-ink-2">Applying works once the careers service is running.</p>` : `<p class="text-ink-2">Loading…</p>`}</div>
      </div>
    </aside>
  </div>`;
  if (!isPreview) applyPanel(j);
}

async function applyPanel(j) {
  const box = $("[data-apply]");
  const { user } = await currentUser();
  if (!user) {
    if (j.status !== "open") { box.innerHTML = `<p class="text-ink-2">This vacancy is no longer taking applications.</p>`; return; }
    signInCard(box, { purpose: "applicant", title: "Sign in to apply", lead: "We'll email you a code. Use the address you want us to contact you on.",
      onDone: () => applyPanel(j) });
    box.firstElementChild.classList.remove("border", "p-6", "sm:p-8");
    return;
  }
  const res = await call(`careers/me/jobs/${encodeURIComponent(j.slug)}`);
  const a = res.body?.application;
  if (a && a.status !== "withdrawn") {
    const [cls, label] = STATUS[a.status] || ["", a.status];
    box.innerHTML = `${signedInBar(user)}
      <p class="mt-4"><span class="tag ${cls}">${label}</span></p>
      <p class="mt-2 text-ink-2">You applied on ${esc(nptDate(a.created_at))}. We'll email you about each step.</p>
      ${a.message ? `<div class="mt-4 rounded-sm bg-canvas p-3"><p class="text-[0.8125rem] font-semibold text-ink-3 uppercase">Message from HR</p><p class="mt-1">${esc(a.message)}</p></div>` : ""}
      ${["submitted", "shortlisted", "interview"].includes(a.status) ? `<button type="button" class="mt-4 text-[0.9375rem] font-semibold text-om-700 hover:underline" data-withdraw>Withdraw my application</button>` : ""}`;
    $("[data-withdraw]", box)?.addEventListener("click", async (e) => {
      if (e.target.dataset.armed !== "1") { e.target.dataset.armed = "1"; e.target.textContent = "Click again to withdraw"; return; }
      await call(`careers/me/jobs/${encodeURIComponent(j.slug)}/withdraw`, { method: "POST" });
      applyPanel(j);
    });
    return;
  }
  if (j.status !== "open") { box.innerHTML = `${signedInBar(user)}<p class="mt-3 text-ink-2">This vacancy is no longer taking applications.</p>`; return; }
  const f = (name, label, attrs = "", type = "text") => `<div><label class="field-label" for="j-${name}">${label}</label><input id="j-${name}" name="${name}" type="${type}" class="field" ${attrs}></div>`;
  box.innerHTML = `${signedInBar(user)}
    <form class="mt-5 space-y-4" data-job-form novalidate>
      ${f("full_name", "Full name", `required maxlength="160" autocomplete="name" value="${esc(user.name && !user.name.includes("@") && user.name !== user.email.split("@")[0] ? user.name : "")}"`)}
      ${f("phone", "Phone", 'required maxlength="30" autocomplete="tel" inputmode="tel"', "tel")}
      ${f("qualification", "Highest qualification", 'maxlength="200" placeholder="e.g. ME Computer Engineering, TU"')}
      ${f("experience_years", "Years of experience", 'maxlength="10" inputmode="numeric"')}
      <div><label class="field-label" for="j-cover_letter">Why you? <span class="font-normal text-ink-3">(optional)</span></label><textarea id="j-cover_letter" name="cover_letter" class="field min-h-28 py-2.5" maxlength="6000"></textarea></div>
      <div><label class="field-label" for="j-cv">CV (PDF, up to 10 MB)</label><input id="j-cv" name="cv" type="file" accept="application/pdf" class="block w-full text-[0.9375rem] file:mr-3 file:rounded-sm file:border file:border-line file:bg-white file:px-3 file:py-2 file:font-semibold" required></div>
      <button class="btn btn-apply w-full" type="submit">Send application</button>
      <p class="text-[0.9375rem] font-semibold text-om-700" role="alert" data-job-error></p>
    </form>`;
  const form = $("[data-job-form]", box);
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const err = $("[data-job-error]", box);
    if (!form.cv.files[0]) { err.textContent = "Attach your CV as a PDF."; return; }
    const btn = form.querySelector('button[type="submit"]');
    btn.disabled = true;
    btn.textContent = "Sending…";
    const res = await call(`careers/me/jobs/${encodeURIComponent(j.slug)}/apply`, { method: "POST", form: new FormData(form) });
    if (res.ok) { applyPanel(j); return; }
    err.textContent = errorText(res);
    btn.disabled = false;
    btn.textContent = "Send application";
  });
}

const slug = location.pathname.match(/^\/careers\/([a-z0-9-]+)\/?$/)?.[1] || new URLSearchParams(location.search).get("j");
if (page === "careers") careers();
if (page === "job") slug ? jobPage(slug) : location.replace("/careers");
