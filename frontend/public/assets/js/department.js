// Department page: one template for every department, filled from
// academics-service (/api/v1/academics/public/departments/<slug>).
// Address: /departments/<slug>  (or /department.html?d=<slug> for local previews)

import { initPhotos, initScrollSpy, initTabs } from "./site.js";

const ICONS = "/assets/img/icons.svg";
const $ = (sel, root = document) => root.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const icon = (id, cls = "icon-sm") => `<svg class="${cls}" aria-hidden="true"><use href="${ICONS}#i-${id}"/></svg>`;
// Editors type plain text; blank lines become paragraphs, single line breaks stay.
const paragraphs = (text, cls = "") => String(text || "").split(/\n\s*\n/).filter((p) => p.trim())
  .map((p) => `<p class="${cls}">${esc(p.trim()).replace(/\n/g, "<br>")}</p>`).join("");
const initials = (name) => String(name || "?").replace(/^(Er|Dr|Mr|Ms|Mrs|Prof)\.?\s+/i, "").split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();
const ordinal = (n) => `${n}${[11, 12, 13].includes(n % 100) ? "th" : ({ 1: "st", 2: "nd", 3: "rd" })[n % 10] || "th"}`;

function slugFromUrl() {
  const m = location.pathname.match(/^\/departments\/([a-z0-9-]+)\/?$/);
  return m ? m[1] : new URLSearchParams(location.search).get("d") || "";
}

async function load(slug) {
  try {
    const res = await fetch(`/api/v1/academics/public/departments/${encodeURIComponent(slug)}`, { headers: { Accept: "application/json" } });
    const json = (res.headers.get("content-type") || "").includes("json");
    if (res.status === 404 && json) return { notFound: true };
    if (res.ok && json) return { department: (await res.json()).department };
  } catch { /* fall through to preview data */ }
  // No backend (static preview): use bundled preview data, clearly labelled.
  try {
    const all = await (await fetch("/assets/data/departments-preview.json")).json();
    const department = all.departments.find((d) => d.slug === slug);
    return department ? { department, preview: true } : { notFound: true };
  } catch {
    return { notFound: true };
  }
}

const SECTIONS = [];
function section(id, title, html, { first = false } = {}) {
  SECTIONS.push({ id, title });
  return `<section id="${id}" class="${first ? "" : "border-t border-line "}py-12 md:py-16" aria-labelledby="${id}-title">
    <h2 id="${id}-title" class="section-title">${esc(title)}</h2>${html}</section>`;
}

function photo(src, alt, cls, { label = "" } = {}) {
  if (!src) return "";
  return `<div class="photo ${cls}"><img src="${esc(src)}" alt="${esc(alt)}" loading="lazy">${label ? `<span class="photo-label">${esc(label)}</span>` : ""}</div>`;
}

function renderHeader(d) {
  document.title = `Department of ${d.name} · NCIT`;
  $('meta[name="description"]')?.setAttribute("content", d.tagline || `Department of ${d.name} at Nepal College of Information Technology.`);
  $('[data-d="crumb"]').textContent = d.name;
  $('[data-d="title"]').textContent = `Department of ${d.name}`;
  $('[data-d="tagline"]').textContent = d.tagline || "";
  const facts = [];
  if (d.hod.name) facts.push(["Head of Department", esc(d.hod.name)]);
  if (d.programmes.length) facts.push(["Programmes", d.programmes.map((p) => esc(p.name)).join("<br>")]);
  if (d.contact.email) facts.push(["Email", `<a class="text-brand-700 hover:underline" href="mailto:${esc(d.contact.email)}">${esc(d.contact.email)}</a>`]);
  if (d.contact.phone) facts.push(["Phone", `<a class="text-brand-700 hover:underline" href="tel:${esc(d.contact.phone.replace(/[^\d+]/g, ""))}">${esc(d.contact.phone)}</a>`]);
  if (d.contact.office) facts.push(["Office", esc(d.contact.office)]);
  $('[data-d="facts"]').innerHTML = facts.map(([k, v]) => `<div class="min-w-0"><dt class="text-ink-3">${k}</dt><dd class="font-semibold break-words">${v}</dd></div>`).join("");
}

function renderOverview(d) {
  const text = d.overview ? `<div class="max-w-[66ch] space-y-4 text-[1.125rem] text-ink-2">${paragraphs(d.overview)}</div>`
    : `<p class="mt-6 text-ink-2">The department hasn't added an overview yet.</p>`;
  const body = d.hero_photo
    ? `<div class="mt-6 grid gap-10 xl:grid-cols-[minmax(0,1fr)_18rem]">${text}${photo(d.hero_photo, `${d.name} at NCIT`, "aspect-[4/3] rounded-sm xl:aspect-[4/5]")}</div>`
    : `<div class="mt-6">${text}</div>`;
  return section("overview", "Overview", body, { first: true });
}

function renderHod(d) {
  if (!d.hod.message && !d.hod.name) return "";
  return section("hod-message", "Message from the Head of Department", `
    <figure class="mt-8 grid gap-8 ${d.hod.photo ? "sm:grid-cols-[10rem_1fr]" : ""}">
      ${photo(d.hod.photo, `${d.hod.name}, ${d.hod.title || "Head of Department"}`, "aspect-[4/5] w-32 rounded-sm sm:w-40 [&>img]:object-top")}
      <div>
        ${d.hod.message ? `<blockquote class="max-w-[60ch] space-y-4 font-serif text-[1.25rem] leading-relaxed text-ink sm:text-[1.375rem]">${paragraphs(d.hod.message)}</blockquote>` : ""}
        <figcaption class="${d.hod.message ? "mt-5" : ""}"><span class="block font-semibold">${esc(d.hod.name)}</span><span class="block text-ink-2">${esc(d.hod.title || `Head of Department, ${d.name}`)}</span></figcaption>
      </div>
    </figure>`);
}

function renderProgrammes(d) {
  if (!d.programmes.length) return "";
  return section("programmes", "Programmes", `<div class="mt-8 divided border-y border-line">${d.programmes.map((p, i) => `
    <article class="grid gap-4 py-6 md:grid-cols-[1fr_auto] md:items-start md:gap-10">
      <div>
        <h3 class="font-serif text-h3 font-semibold">${esc(p.name)}</h3>
        <p class="mt-2 text-ink-2">${p.duration_years} years · ${p.semester_count} semesters${p.affiliation ? ` · ${esc(p.affiliation)}` : ""}</p>
        ${p.eligibility ? `<p class="mt-1 text-[0.9375rem] text-ink-3"><span class="font-semibold text-ink-2">Eligibility:</span> ${esc(p.eligibility)}</p>` : ""}
        ${p.description ? `<div class="mt-3 max-w-[64ch] space-y-3 text-ink-2">${paragraphs(p.description)}</div>` : ""}
      </div>
      <div class="flex flex-wrap gap-3"><a class="btn btn-outline btn-sm" href="#courses" data-show-programme="${i}">See courses</a><a class="btn btn-apply btn-sm" href="/#apply">Apply</a></div>
    </article>`).join("")}</div>`);
}

function semesterTable(sem) {
  return `<table class="data-table mt-2">
    <caption class="sr-only">${ordinal(sem.semester)} semester courses</caption>
    <thead><tr><th scope="col" class="w-28">Code</th><th scope="col">Course</th><th scope="col" class="w-24 text-right">Credits</th></tr></thead>
    <tbody>${sem.courses.map((c) => `<tr><td class="text-ink-3">${esc(c.code)}</td><td class="font-semibold">${esc(c.title)}</td><td class="text-right">${esc(c.credits)}</td></tr>`).join("")}</tbody>
    <tfoot><tr><td></td><td class="pt-4 font-semibold">Total</td><td class="pt-4 text-right font-semibold">${esc(sem.total_credits)}</td></tr></tfoot>
  </table>`;
}

function coursesPanel(p, pi) {
  const tabs = [], panels = [];
  for (let n = 1; n <= p.semester_count; n++) {
    const sem = p.semesters.find((s) => s.semester === n);
    const id = `p${pi}-s${n}`;
    tabs.push(`<button role="tab" class="tab" id="tab-${id}" aria-controls="sem-${id}" aria-selected="${n === 1}" ${n === 1 ? "" : 'tabindex="-1"'}>Semester ${n}</button>`);
    panels.push(`<div id="sem-${id}" role="tabpanel" aria-labelledby="tab-${id}" tabindex="0" ${n === 1 ? "" : "hidden"}>${sem?.courses.length ? semesterTable(sem) : `<p class="py-10 text-ink-2">Courses for semester ${n} haven't been published yet.</p>`}</div>`);
  }
  return `
    ${p.syllabus_url ? `<a class="link-arrow mt-3" href="${esc(p.syllabus_url)}">Full syllabus ${icon("download")}</a>` : ""}
    <div role="tablist" aria-label="Semester" class="no-scrollbar mt-6 flex overflow-x-auto border-b border-line">${tabs.join("")}</div>
    ${panels.join("")}`;
}

function renderCourses(d) {
  if (!d.programmes.length) return "";
  const picker = d.programmes.length > 1
    ? `<div class="mt-6 flex flex-wrap gap-2" role="group" aria-label="Programme">${d.programmes.map((p, i) => `<button type="button" class="rounded-sm border px-4 py-2 font-semibold transition-colors aria-pressed:border-brand-700 aria-pressed:bg-brand-50 aria-pressed:text-brand-800 border-line text-ink-2 hover:border-brand-700" data-programme="${i}" aria-pressed="${i === 0}">${esc(p.name)}</button>`).join("")}</div>`
    : `<p class="mt-3 text-ink-2">${esc(d.programmes[0].name)}</p>`;
  return section("courses", "Courses by semester", `${picker}<div data-courses-panel>${coursesPanel(d.programmes[0], 0)}</div>`);
}

function renderFaculty(d) {
  if (!d.faculty.length) return "";
  return section("faculty", "Faculty", `<ul class="mt-8 grid grid-cols-2 gap-x-6 gap-y-10 sm:grid-cols-3 xl:grid-cols-4">${d.faculty.map((f) => `
    <li>
      ${f.photo ? photo(f.photo, f.name, "aspect-[4/5] rounded-sm [&>img]:object-top") : `<div class="flex aspect-[4/5] items-center justify-center rounded-sm bg-brand-100 font-serif text-[2rem] font-semibold text-brand-800" aria-hidden="true">${esc(initials(f.name))}</div>`}
      <p class="mt-3 font-semibold">${esc(f.name)}</p>
      <p class="text-[0.9375rem] text-ink-2">${esc([f.designation, f.specialization].filter(Boolean).join(" · "))}</p>
      ${f.email ? `<a class="mt-1 inline-block max-w-full truncate text-[0.875rem] text-brand-700 hover:underline" href="mailto:${esc(f.email)}">${esc(f.email)}</a>` : ""}
    </li>`).join("")}</ul>`);
}

function renderLabs(d) {
  if (!d.labs.length) return "";
  return section("labs", "Labs", `<ul class="mt-8 grid gap-x-10 sm:grid-cols-2">${d.labs.map((l) => `
    <li class="border-b border-line py-5">
      ${l.photo ? photo(l.photo, l.name, "mb-4 aspect-[16/9] rounded-sm") : ""}
      <h3 class="font-semibold">${esc(l.name)}</h3>${l.description ? `<div class="mt-1 space-y-2 text-ink-2">${paragraphs(l.description)}</div>` : ""}
    </li>`).join("")}</ul>`);
}

function renderTestimonials(d) {
  if (!d.testimonials.length) return "";
  return section("students", "What students say", `<div class="mt-8 grid gap-6 md:grid-cols-2">${d.testimonials.map((t) => `
    <figure class="flex flex-col rounded-md bg-canvas p-6 sm:p-8">
      ${icon("quote", "h-8 w-8 text-brand-200")}
      <blockquote class="mt-3 flex-1 space-y-3 font-serif text-[1.1875rem] leading-relaxed text-ink">${paragraphs(t.quote)}</blockquote>
      <figcaption class="mt-6 flex items-center gap-4">
        ${t.photo ? photo(t.photo, "", "h-12 w-12 flex-none rounded-full") : `<span class="flex h-12 w-12 flex-none items-center justify-center rounded-full bg-brand-100 font-semibold text-brand-800" aria-hidden="true">${esc(initials(t.student_name))}</span>`}
        <div><span class="block font-semibold">${esc(t.student_name)}</span><span class="block text-[0.9375rem] text-ink-2">${esc(t.programme_label)}</span></div>
      </figcaption>
    </figure>`).join("")}</div>`);
}

function render(d) {
  renderHeader(d);
  SECTIONS.length = 0;
  const html = [renderOverview(d), renderHod(d), renderProgrammes(d), renderCourses(d), renderFaculty(d), renderLabs(d), renderTestimonials(d)].join("");
  const updated = new Date(d.updated_at).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });
  $('[data-d="sections"]').innerHTML = html + `
    <p class="mb-12 flex flex-wrap items-center gap-x-2 gap-y-1 border-t border-line pt-5 text-[0.875rem] text-ink-3">
      ${icon("history")} Maintained by the Department of ${esc(d.name)} · Last updated <time datetime="${esc(d.updated_at)}">${esc(updated)}</time>
    </p>`;
  $('[data-d="nav"]').innerHTML = SECTIONS.map((s) => `<li><a class="block rounded-sm px-3 py-2 font-semibold whitespace-nowrap text-ink-2 hover:text-brand-700 aria-[current=true]:bg-brand-50 aria-[current=true]:text-brand-800 lg:px-4" href="#${s.id}">${esc(s.id === "hod-message" ? "Message from the HOD" : s.title)}</a></li>`).join("");

  // programme switcher for the course tables
  const panel = $("[data-courses-panel]");
  const showProgramme = (i) => {
    panel.innerHTML = coursesPanel(d.programmes[i], i);
    initTabs(panel);
    document.querySelectorAll("[data-programme]").forEach((b) => b.setAttribute("aria-pressed", String(Number(b.dataset.programme) === i)));
  };
  document.querySelectorAll("[data-programme]").forEach((b) => b.addEventListener("click", () => showProgramme(Number(b.dataset.programme))));
  document.querySelectorAll("[data-show-programme]").forEach((a) => a.addEventListener("click", () => showProgramme(Number(a.dataset.showProgramme))));
  if (panel) initTabs(panel);
  initPhotos($('[data-d="sections"]'));
  initScrollSpy();
  if (location.hash) document.getElementById(location.hash.slice(1))?.scrollIntoView();
}

async function start() {
  const slug = slugFromUrl();
  const result = slug ? await load(slug) : { notFound: true };
  if (result.notFound) {
    $('[data-d="title"]').textContent = "Department not found";
    $('[data-d="crumb"]').textContent = "Not found";
    $('[data-d="body"]').hidden = true;
    $('[data-d="not-found"]').classList.remove("hidden");
    return;
  }
  if (result.preview) $('[data-d="preview-banner"]').classList.remove("hidden");
  render(result.department);
}

start();
