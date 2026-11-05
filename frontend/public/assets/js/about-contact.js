// About (leadership and facilities from content-service), Contact (the message
// form) and the Faculty directory (from academics-service).

import { initPhotos } from "./site.js";
import { esc, icon, loadContent } from "./content-shared.js";

const $ = (s, root = document) => root.querySelector(s);
const page = document.body.dataset.page;

async function about() {
  const { data } = await loadContent("home");
  const leaders = $("[data-about-leaders]"), facilities = $("[data-about-facilities]");
  if (!data) {
    leaders.innerHTML = `<li class="text-ink-2"><a class="font-semibold text-brand-700 hover:underline" href="/leadership">Messages from the leadership</a></li>`;
    facilities.innerHTML = "";
    return;
  }
  leaders.innerHTML = data.leadership.map((m) => `<li class="flex gap-4">
      <div class="photo aspect-[4/5] w-20 flex-none rounded-sm">${m.photo ? `<img src="${esc(m.photo)}" alt="" class="object-top" loading="lazy">` : ""}</div>
      <div><p class="font-semibold">${esc(m.person_name)}</p><p class="text-[0.9375rem] text-ink-2">${esc(m.role_title)}</p>
      <a class="link-arrow mt-2 text-[0.9375rem]" href="/leadership#${esc(m.position)}">Message ${icon("arrow-right")}</a></div></li>`).join("");
  facilities.innerHTML = data.facilities.map((f) => `<li class="flex gap-3"><span class="mt-0.5 text-brand-700">${icon(f.icon || "building-2", "icon")}</span>
      <div><p class="font-semibold">${esc(f.name)}</p>${f.description ? `<p class="text-[0.9375rem] text-ink-2">${esc(f.description)}</p>` : ""}</div></li>`).join("");
  initPhotos(leaders);
}

function contact() {
  const form = $("[data-contact]");
  const status = $("[data-contact-status]");
  const csrf = () => document.cookie.split("; ").find((c) => c.startsWith("ncit_csrf="))?.split("=")[1] || "";
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(form));
    status.className = "text-[0.9375rem] font-semibold text-om-700";
    if (!data.name.trim()) { status.textContent = "Tell us your name."; form.name.focus(); return; }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.email.trim())) { status.textContent = "Enter an email address we can reply to."; form.email.focus(); return; }
    if (data.message.trim().length < 10) { status.textContent = "Write a little more so we can help."; form.message.focus(); return; }
    const btn = form.querySelector('button[type="submit"]');
    btn.disabled = true;
    status.className = "text-[0.9375rem] text-ink-2";
    status.textContent = "Sending…";
    let res;
    try {
      res = await fetch("/api/v1/content/public/contact", { method: "POST", headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf() }, body: JSON.stringify(data) });
    } catch { res = null; }
    btn.disabled = false;
    if (res?.ok) {
      form.reset();
      status.className = "text-[0.9375rem] font-semibold text-leaf-700";
      status.textContent = "Thank you. Your message has been sent; we'll reply by email.";
      return;
    }
    const body = res ? await res.json().catch(() => null) : null;
    status.className = "text-[0.9375rem] font-semibold text-om-700";
    status.textContent = res?.status === 429 ? "Too many messages from here. Try again in a few minutes, or call us."
      : body?.error?.message || "The message couldn't be sent. Email info@ncit.edu.np instead.";
  });
}

async function facultyDirectory() {
  const body = $('[data-c="body"]');
  let items = null;
  try {
    const res = await fetch("/api/v1/academics/public/faculty", { headers: { Accept: "application/json" } });
    if (res.ok && (res.headers.get("content-type") || "").includes("json")) items = (await res.json()).items;
  } catch { /* preview below */ }
  if (!items) {
    const p = await fetch("/assets/data/departments-preview.json").then((r) => r.json()).catch(() => null);
    const depts = p?.departments || [];
    items = depts.flatMap((d) => (d.faculty || []).map((f) => ({ ...f, department: { slug: d.slug, name: d.name } }))).sort((a, b) => a.name.localeCompare(b.name));
    if (items.length) $('[data-c="preview-banner"]').classList.remove("hidden");
  }
  const departments = [...new Map(items.map((f) => [f.department.slug, f.department.name])).entries()].sort((a, b) => a[1].localeCompare(b[1]));
  const params = new URLSearchParams(location.search);
  body.innerHTML = `<form class="grid gap-3 rounded-sm border border-line bg-canvas p-4 sm:grid-cols-[1fr_auto]" role="search" data-filter>
      <div><label class="sr-only" for="f-q">Search faculty</label><input id="f-q" name="q" type="search" class="field" placeholder="Name or subject" value="${esc(params.get("q") || "")}"></div>
      <div><label class="sr-only" for="f-dept">Department</label><select id="f-dept" name="dept" class="field"><option value="">All departments</option>${departments.map(([s, n]) => `<option value="${esc(s)}" ${params.get("dept") === s ? "selected" : ""}>${esc(n)}</option>`).join("")}</select></div>
    </form>
    <p class="mt-6 text-[0.9375rem] text-ink-3" aria-live="polite" data-count></p>
    <ul class="mt-4 grid gap-x-8 gap-y-8 sm:grid-cols-2 lg:grid-cols-3" data-people></ul>`;
  const render = () => {
    const q = $("#f-q").value.trim().toLowerCase(), dept = $("#f-dept").value;
    const shown = items.filter((f) => (!dept || f.department.slug === dept) && (!q || `${f.name} ${f.designation} ${f.specialization}`.toLowerCase().includes(q)));
    $("[data-count]").textContent = `${shown.length} ${shown.length === 1 ? "person" : "people"}`;
    $("[data-people]").innerHTML = shown.map((f) => `<li class="flex gap-4">
        <div class="photo aspect-[4/5] w-20 flex-none rounded-sm">${f.photo ? `<img src="${esc(f.photo)}" alt="" class="object-top" loading="lazy">` : `<span class="absolute inset-0 grid place-items-center bg-brand-50 font-serif text-[1.5rem] font-semibold text-brand-700" aria-hidden="true">${esc(f.name.replace(/^(Dr|Er|Mr|Ms|Mrs|Prof)\.?\s+/i, "").split(/\s+/).map((w) => w[0]).slice(0, 2).join(""))}</span>`}</div>
        <div class="min-w-0"><p class="font-semibold">${esc(f.name)}</p><p class="text-[0.9375rem] text-ink-2">${esc(f.designation)}</p>
        ${f.specialization ? `<p class="text-[0.875rem] text-ink-3">${esc(f.specialization)}</p>` : ""}
        <p class="mt-1 text-[0.875rem]"><a class="font-semibold text-brand-700 hover:underline" href="/departments/${esc(f.department.slug)}">${esc(f.department.name)}</a>${f.email ? ` · <a class="text-brand-700 hover:underline" href="mailto:${esc(f.email)}">Email</a>` : ""}</p></div></li>`).join("")
      || `<li class="text-ink-2">No one matches that search.</li>`;
    initPhotos($("[data-people]"));
    const next = new URLSearchParams(Object.entries({ q, dept }).filter(([, v]) => v));
    history.replaceState(null, "", `${location.pathname}${next.toString() ? `?${next}` : ""}`);
  };
  $("[data-filter]").addEventListener("input", render);
  $("[data-filter]").addEventListener("submit", (e) => { e.preventDefault(); render(); });
  render();
}

if (page === "about") about();
if (page === "contact") contact();
if (page === "faculty") facultyDirectory();
