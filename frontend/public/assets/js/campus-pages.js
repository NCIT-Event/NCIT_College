// Events (list, calendar, event page with registration) and Clubs (list,
// club page with join request). Reads from event-service and eca-service.

import { initPhotos } from "./site.js";
import { CLUB_CATEGORIES, EVENT_CATEGORIES, esc, icon, loadPublic, loginUrl, nepal, paragraphs, session, when } from "./campus-shared.js";

const $ = (sel, root = document) => root.querySelector(sel);
const body = $('[data-c="body"]');
const page = document.body.dataset.page;
const params = new URLSearchParams(location.search);
const pad2 = (n) => String(n).padStart(2, "0");
const DAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

function showPreview(flag) {
  if (flag) $('[data-c="preview-banner"]').classList.remove("hidden");
}

function crumb(title) {
  $('[data-c="crumbs"]').insertAdjacentHTML("afterend",
    `<li aria-hidden="true"><svg class="icon-sm"><use href="/assets/img/icons.svg#i-chevron-right"/></svg></li><li><span aria-current="page" class="text-ink-2">${esc(title)}</span></li>`);
}

function notFound(what, back, label) {
  $('[data-c="title"]').textContent = `${what} not found`;
  $('[data-c="lead"]').textContent = "It may have been removed or not published yet.";
  body.innerHTML = `<a class="btn btn-primary" href="${back}">${label}</a>`;
}

const chip = (href, label, active) =>
  `<a href="${href}" class="inline-flex min-h-10 items-center rounded-sm border px-4 font-semibold ${active ? "border-brand-700 bg-brand-50 text-brand-800" : "border-line text-ink-2 hover:border-brand-700"}" ${active ? 'aria-current="page"' : ""}>${label}</a>`;

function qs(next) {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(next)) if (v) p.set(k, v);
  const s = p.toString();
  return s ? `?${s}` : "";
}

/* ---------- events ---------- */

function seats(e) {
  const r = e.registration;
  if (!r || r.state === "off") return "";
  if (r.state === "closed") return `<span class="tag">Registration closed</span>`;
  if (r.state === "full") return `<span class="tag tag-amber">Full · waiting list</span>`;
  return `<span class="tag tag-leaf">Registration open${r.spots_left != null ? ` · ${r.spots_left} ${r.spots_left === 1 ? "place" : "places"} left` : ""}</span>`;
}

function eventRow(e, { past = false } = {}) {
  return `<li class="group relative flex gap-5 py-6">
    <div class="date-block ${past ? "opacity-70" : ""}"><span class="d">${pad2(nepal.day(e.start_at))}</span><span class="m">${nepal.month(e.start_at)}</span></div>
    <div class="min-w-0 flex-1">
      <p class="flex flex-wrap items-center gap-2 text-[0.875rem] text-ink-3"><span class="tag">${esc(EVENT_CATEGORIES[e.category] || "Event")}</span>${past ? "" : seats(e)}</p>
      <h2 class="mt-2 text-[1.25rem] leading-snug font-semibold"><a href="/events/${esc(e.slug)}" class="after:absolute after:inset-0 group-hover:text-brand-700">${esc(e.title)}</a></h2>
      <p class="mt-1 text-[0.9375rem] text-ink-2">${esc(when(e))}${e.venue ? ` · ${esc(e.venue)}` : ""}${e.organizer ? ` · ${esc(e.organizer)}` : ""}</p>
      ${e.summary ? `<p class="mt-2 max-w-[66ch] text-ink-2">${esc(e.summary)}</p>` : ""}
    </div>
  </li>`;
}
function eventTabs(view, category) {
  const tab = (v, label, iconId) => {
    const active = view === v;
    return `<a href="/events${qs({ view: v === "upcoming" ? "" : v, category })}" class="inline-flex min-h-11 items-center gap-2 border-b-2 px-1 font-semibold ${active ? "border-brand-700 text-brand-800" : "border-transparent text-ink-2 hover:text-brand-700"}" ${active ? 'aria-current="page"' : ""}>${icon(iconId)}${label}</a>`;
  };
  const cats = [["", "All"], ...Object.entries(EVENT_CATEGORIES)].map(([k, label]) =>
    chip(`/events${qs({ view: view === "upcoming" ? "" : view, category: k, month: params.get("month") })}`, label, k === category)).join("");
  return `<nav class="flex flex-wrap gap-x-6 border-b border-line" aria-label="Event views">${tab("upcoming", "Upcoming", "calendar")}${tab("past", "Past", "history")}${tab("calendar", "Month calendar", "calendar-days")}</nav>
    <nav class="mt-6 flex flex-wrap gap-2" aria-label="Event categories">${cats}</nav>`;
}

async function eventsPage() {
  const view = ["past", "calendar"].includes(params.get("view")) ? params.get("view") : "upcoming";
  const category = EVENT_CATEGORIES[params.get("category")] ? params.get("category") : "";
  if (view === "calendar") return calendarView(category);
  const page = Math.max(Number(params.get("page") || 1), 1);
  const { data, preview } = await loadPublic("events", `events${qs({ when: view === "past" ? "past" : "", category, page: page > 1 ? page : "" })}`);
  showPreview(preview);
  if (!data) { body.innerHTML = `${eventTabs(view, category)}<p class="mt-8 text-ink-2">Events couldn't be loaded. Try again in a minute.</p>`; return; }
  const pages = Math.ceil(data.total / data.per_page);
  const link = (p, label) => `<a class="btn btn-outline btn-sm" href="/events${qs({ view: view === "upcoming" ? "" : view, category, page: p })}">${label}</a>`;
  body.innerHTML = `${eventTabs(view, category)}
    ${data.items.length ? `<ul class="mt-6 divided border-y border-line">${data.items.map((e) => eventRow(e, { past: view === "past" })).join("")}</ul>`
      : `<p class="mt-8 text-ink-2">${view === "past" ? "No past events in this category." : "No upcoming events in this category yet. Check back soon."}</p>`}
    ${pages > 1 ? `<nav class="mt-10 flex items-center justify-between gap-4" aria-label="Pages"><span class="text-ink-2">Page ${data.page} of ${pages}</span><span class="flex gap-2">${data.page > 1 ? link(data.page - 1, "Previous") : ""}${data.page < pages ? link(data.page + 1, "Next") : ""}</span></nav>` : ""}`;
}

function shiftMonth(ym, by) {
  const [y, m] = ym.split("-").map(Number);
  const d = new Date(Date.UTC(y, m - 1 + by, 1));
  return `${d.getUTCFullYear()}-${pad2(d.getUTCMonth() + 1)}`;
}

async function calendarView(category) {
  const month = /^20\d\d-(0[1-9]|1[0-2])$/.test(params.get("month") || "") ? params.get("month") : nepal.thisMonth();
  const { data, preview } = await loadPublic("events", `calendar?month=${month}`);
  showPreview(preview);
  const head = eventTabs("calendar", category);
  if (!data) { body.innerHTML = `${head}<p class="mt-8 text-ink-2">The calendar couldn't be loaded. Try again in a minute.</p>`; return; }
  const items = data.items.filter((e) => !category || e.category === category);
  // which days each event covers (multi-day events show on every day)
  const byDay = {};
  for (const e of items) {
    const start = new Date(nepal.key(e.start_at) + "T00:00:00Z");
    const end = new Date(nepal.key(e.end_at || e.start_at) + "T00:00:00Z");
    for (let d = new Date(start); d <= end; d.setUTCDate(d.getUTCDate() + 1)) {
      const key = d.toISOString().slice(0, 10);
      if (key.startsWith(month)) (byDay[key] ??= []).push(e);
    }
  }
  const [y, m] = month.split("-").map(Number);
  const first = new Date(Date.UTC(y, m - 1, 1)).getUTCDay();
  const days = new Date(Date.UTC(y, m, 0)).getUTCDate();
  const today = nepal.key(new Date().toISOString());
  const cells = [];
  for (let i = 0; i < first; i++) cells.push(`<div class="hidden min-h-24 bg-canvas sm:block" aria-hidden="true"></div>`);
  for (let d = 1; d <= days; d++) {
    const key = `${month}-${pad2(d)}`;
    const evs = byDay[key] || [];
    const isToday = key === today;
    cells.push(`<div class="min-h-14 bg-white p-1.5 sm:min-h-24 sm:p-2 ${evs.length ? "" : "max-sm:hidden"}">
      <p class="flex items-center gap-2 text-[0.875rem] font-semibold ${isToday ? "text-om-700" : "text-ink-2"}"><span class="sm:hidden">${DAY_NAMES[new Date(key + "T00:00:00Z").getUTCDay()]}</span>${d}${isToday ? `<span class="text-[0.75rem]">Today</span>` : ""}</p>
      <ul class="mt-1 space-y-1">${evs.map((e) => `<li><a href="/events/${esc(e.slug)}" class="block rounded-sm bg-brand-50 px-2 py-1 text-[0.8125rem] leading-snug font-semibold text-brand-800 hover:bg-brand-100 sm:truncate">${esc(e.title)}</a></li>`).join("")}</ul>
    </div>`);
  }
  const trailing = (7 - ((first + days) % 7)) % 7;
  for (let i = 0; i < trailing; i++) cells.push(`<div class="hidden min-h-24 bg-canvas sm:block" aria-hidden="true"></div>`);
  const nav = (by, label, iconId) => `<a class="btn btn-outline btn-sm" href="/events${qs({ view: "calendar", month: shiftMonth(month, by), category })}" aria-label="${label}">${by < 0 ? icon(iconId) : ""}${label}${by > 0 ? icon(iconId) : ""}</a>`;
  body.innerHTML = `${head}
    <div class="mt-8 flex items-center justify-between gap-4">
      <h2 class="font-serif text-h3 font-semibold">${nepal.monthName(month)}</h2>
      <div class="flex gap-2">${nav(-1, "Previous", "chevron-left")}${nav(1, "Next", "chevron-right")}</div>
    </div>
    <p class="mt-1 text-[0.875rem] text-ink-3">Times are Nepal time.</p>
    <div class="mt-4 grid grid-cols-1 gap-px overflow-hidden rounded-sm border border-line bg-line sm:grid-cols-7">
      ${DAY_NAMES.map((d) => `<div class="hidden bg-canvas px-2 py-2 text-[0.8125rem] font-semibold text-ink-3 uppercase sm:block">${d}</div>`).join("")}
      ${cells.join("")}
    </div>
    ${items.length ? "" : `<p class="mt-6 text-ink-2">No events in ${nepal.monthName(month)}${category ? " in this category" : ""}.</p>`}`;
}
async function eventPage(slug) {
  const { data, preview } = await loadPublic("events", `events/${encodeURIComponent(slug)}`);
  showPreview(preview);
  if (!data) { notFound("Event", "/events", "All events"); return; }
  const e = data.event;
  document.title = `${e.title} · NCIT`;
  $('meta[name="description"]')?.setAttribute("content", e.summary || e.title);
  crumb(e.title);
  $('[data-c="title"]').textContent = e.title;
  $('[data-c="lead"]').innerHTML = `<span class="tag mr-2 align-middle">${esc(EVENT_CATEGORIES[e.category] || "Event")}</span>${esc(when(e))}`;
  // <dt>/<dd> must be direct children of the row, so the icon sits inside the <dt>
  const fact = (iconId, label, value) => value ? `<div class="relative py-3 pl-9"><dt class="text-[0.875rem] text-ink-3"><span class="absolute top-3.5 left-0 text-brand-700">${icon(iconId, "icon")}</span>${label}</dt><dd class="font-semibold">${value}</dd></div>` : "";
  body.innerHTML = `<div class="grid gap-12 lg:grid-cols-[1fr_22rem] lg:gap-16">
    <article class="min-w-0 max-w-[46rem]">
      ${e.cover ? `<div class="photo mb-8 aspect-[16/9] rounded-sm"><img src="${esc(e.cover)}" alt="${esc(e.cover_alt)}"></div>` : ""}
      ${e.summary ? `<p class="font-serif text-[1.375rem] leading-snug text-ink">${esc(e.summary)}</p>` : ""}
      <div class="mt-6 space-y-5 text-[1.125rem] leading-relaxed text-ink-2">${paragraphs(e.body)}</div>
      <div class="mt-8 flex flex-wrap gap-3">
        ${e.attachment ? `<a class="btn btn-outline" href="${esc(e.attachment)}">${icon("download")}Programme (PDF)</a>` : ""}
        ${e.external_url ? `<a class="btn btn-outline" href="${esc(e.external_url)}" ${e.external_url.startsWith("/") ? "" : 'rel="noopener" target="_blank"'}>${icon("external-link")}More information</a>` : ""}
      </div>
      <p class="mt-12 border-t border-line pt-6"><a class="link-arrow" href="/events">${icon("chevron-left")} All events</a></p>
    </article>
    <aside class="lg:sticky lg:top-28 lg:self-start" aria-label="Event details">
      <div class="rounded-sm border border-line bg-white p-6">
        <dl class="divided">
          ${fact("calendar", "When (Nepal time)", esc(when(e)).replace(" · ", "<br>"))}
          ${fact("map-pin", "Where", esc(e.venue))}
          ${fact("users", "Organised by", esc(e.organizer))}
        </dl>
        <div class="mt-4 border-t border-line pt-5" data-register aria-live="polite"></div>
      </div>
    </aside>
  </div>`;
  initPhotos(body);
  registerPanel(e, preview);
}

async function registerPanel(e, preview) {
  const box = $("[data-register]");
  const r = e.registration;
  const places = r.capacity ? `<p class="text-[0.9375rem] text-ink-2">${r.taken} of ${r.capacity} places taken${r.state === "full" ? ". New sign-ups join the waiting list." : "."}</p>` : "";
  const closes = `<p class="mt-1 text-[0.875rem] text-ink-3">Registration closes ${esc(nepal.date(r.closes_at))}, ${nepal.time(r.closes_at)}.</p>`;
  if (r.state === "off") { box.innerHTML = `<p class="font-semibold">No registration needed.</p><p class="mt-1 text-ink-2">Just come along.</p>`; return; }
  if (preview) { box.innerHTML = `${places}<button class="btn btn-primary mt-4 w-full" disabled>Register</button><p class="mt-2 text-[0.875rem] text-ink-3">Registration works once the events service is running.</p>`; return; }

  const mine = await session(`events/me/events/${encodeURIComponent(e.slug)}`);
  const signedIn = mine.ok;
  const reg = mine.body?.registration;
  const live = mine.body?.event?.registration || r;
  const placesNow = live.capacity ? `<p class="text-[0.9375rem] text-ink-2">${live.taken} of ${live.capacity} places taken${live.state === "full" ? ". New sign-ups join the waiting list." : "."}</p>` : "";

  if (reg) {
    const waiting = reg.status === "waitlisted";
    box.innerHTML = `<p class="flex items-center gap-2 font-semibold ${waiting ? "text-amber-700" : "text-leaf-700"}">${icon(waiting ? "clock" : "check", "icon")}${waiting ? `You're number ${reg.waitlist_position} on the waiting list` : "You're registered"}</p>
      <p class="mt-1 text-[0.9375rem] text-ink-2">${waiting ? "If a place frees up you move up automatically; check back here." : "See you there. You can find this under My activity in your dashboard."}</p>
      <button type="button" class="btn btn-outline btn-sm mt-4" data-cancel>${waiting ? "Leave the waiting list" : "Cancel my registration"}</button>
      <p class="mt-2 text-[0.875rem] text-om-700" data-msg></p>`;
    const btn = $("[data-cancel]", box);
    btn.addEventListener("click", async () => {
      if (!btn.dataset.armed) { btn.dataset.armed = "1"; btn.textContent = "Click again to confirm"; return; }
      btn.disabled = true;
      const res = await session(`events/me/events/${encodeURIComponent(e.slug)}/register`, { method: "DELETE" });
      if (res.ok) registerPanel({ ...e, registration: res.body.event.registration }, false);
      else { $("[data-msg]", box).textContent = res.body?.error?.message || "That didn't work. Try again."; btn.disabled = false; }
    });
    return;
  }
  if (live.state === "closed") { box.innerHTML = `<p class="font-semibold">Registration has closed.</p>${placesNow}`; return; }
  const label = live.state === "full" ? "Join the waiting list" : "Register";
  if (!signedIn) {
    box.innerHTML = `${placesNow}<a class="btn btn-primary mt-4 w-full" href="${loginUrl()}">${icon("log-in")}Sign in to ${label.toLowerCase()}</a><p class="mt-2 text-[0.875rem] text-ink-3">Use your @ncit.edu.np account.</p>${closes}`;
    return;
  }
  box.innerHTML = `${placesNow}<button type="button" class="btn btn-primary mt-4 w-full" data-go>${label}</button><p class="mt-2 text-[0.875rem] text-om-700" data-msg></p>${closes}`;
  const go = $("[data-go]", box);
  go.addEventListener("click", async () => {
    go.disabled = true;
    go.textContent = "Registering…";
    const res = await session(`events/me/events/${encodeURIComponent(e.slug)}/register`, { method: "POST" });
    if (res.ok || res.body?.error?.code === "already_registered") { registerPanel(e, false); return; }
    $("[data-msg]", box).textContent = res.body?.error?.message || "That didn't work. Try again.";
    go.disabled = false;
    go.textContent = label;
  });
}

/* ---------- clubs ---------- */

const monogram = (name) => esc(name.split(/\s+/).filter((w) => /^[A-Za-z]/.test(w) && w !== "and").map((w) => w[0]).slice(0, 2).join(""));

function clubCard(c) {
  return `<li class="group relative flex flex-col overflow-hidden rounded-sm border border-line bg-white transition-colors hover:border-brand-700">
    <div class="photo aspect-[16/9]">${c.photo ? `<img src="${esc(c.photo)}" alt="${esc(c.photo_alt)}" loading="lazy">` : `<span class="absolute inset-0 grid place-items-center bg-brand-50 font-serif text-[2.5rem] font-semibold text-brand-700" aria-hidden="true">${monogram(c.name)}</span>`}</div>
    <div class="flex flex-1 flex-col p-5">
      <p><span class="tag">${esc(CLUB_CATEGORIES[c.category] || "Club")}</span></p>
      <h2 class="mt-3 font-serif text-[1.375rem] leading-snug font-semibold"><a href="/clubs/${esc(c.slug)}" class="after:absolute after:inset-0 group-hover:text-brand-700">${esc(c.name)}</a></h2>
      ${c.tagline ? `<p class="mt-2 text-ink-2">${esc(c.tagline)}</p>` : ""}
      <p class="mt-auto flex flex-wrap gap-x-4 gap-y-1 pt-4 text-[0.875rem] text-ink-3">
        <span class="inline-flex items-center gap-1.5">${icon("users")}${c.member_count} ${c.member_count === 1 ? "member" : "members"}</span>
        ${c.meeting_info ? `<span class="inline-flex items-center gap-1.5">${icon("clock")}${esc(c.meeting_info)}</span>` : ""}
      </p>
    </div>
  </li>`;
}

async function clubsPage() {
  const category = CLUB_CATEGORIES[params.get("category")] ? params.get("category") : "";
  const [{ data, preview }, acts] = await Promise.all([
    loadPublic("eca", `clubs${qs({ category })}`), loadPublic("eca", "activities?limit=4")]);
  showPreview(preview);
  const cats = [["", "All"], ...Object.entries(CLUB_CATEGORIES)].map(([k, label]) => chip(`/clubs${qs({ category: k })}`, label, k === category)).join("");
  if (!data) { body.innerHTML = `<p class="text-ink-2">Clubs couldn't be loaded. Try again in a minute.</p>`; return; }
  const recent = acts.data?.items || [];
  body.innerHTML = `<nav class="flex flex-wrap gap-2" aria-label="Club categories">${cats}</nav>
    ${data.items.length ? `<ul class="mt-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">${data.items.map(clubCard).join("")}</ul>` : `<p class="mt-8 text-ink-2">No clubs in this category yet.</p>`}
    ${recent.length && !category ? `<section class="mt-16 border-t border-line pt-12" aria-labelledby="recent-title">
      <h2 id="recent-title" class="section-title">Recent club activities</h2>
      <ul class="mt-6 grid gap-x-8 gap-y-10 sm:grid-cols-2">${recent.map(activityItem).join("")}</ul>
    </section>` : ""}`;
  initPhotos(body);
}

function activityItem(a, { showClub = true } = {}) {
  return `<li class="flex gap-5">
    ${a.photo ? `<div class="photo aspect-square w-24 flex-none rounded-sm sm:w-28"><img src="${esc(a.photo)}" alt="${esc(a.photo_alt)}" loading="lazy"></div>` : ""}
    <div class="min-w-0">
      <p class="text-[0.875rem] text-ink-3">${a.happened_on ? esc(nepal.date(a.happened_on)) : ""}${showClub && a.club ? ` · <a class="font-semibold text-brand-700 hover:underline" href="/clubs/${esc(a.club.slug)}">${esc(a.club.name)}</a>` : ""}</p>
      <h3 class="mt-1 font-semibold leading-snug">${esc(a.title)}</h3>
      ${a.body ? `<div class="mt-1 space-y-2 text-[0.9375rem] text-ink-2">${paragraphs(a.body)}</div>` : ""}
    </div>
  </li>`;
}

async function clubPage(slug) {
  const { data, preview } = await loadPublic("eca", `clubs/${encodeURIComponent(slug)}`);
  showPreview(preview);
  if (!data) { notFound("Club", "/clubs", "All clubs"); return; }
  const c = data.club;
  document.title = `${c.name} · NCIT`;
  $('meta[name="description"]')?.setAttribute("content", c.tagline || c.name);
  crumb(c.name);
  $('[data-c="title"]').textContent = c.name;
  $('[data-c="lead"]').innerHTML = `<span class="tag mr-2 align-middle">${esc(CLUB_CATEGORIES[c.category] || "Club")}</span>${esc(c.tagline)}`;
  const fact = (iconId, label, value) => value ? `<div class="relative min-w-0 py-3 pl-9"><dt class="text-[0.875rem] text-ink-3"><span class="absolute top-3.5 left-0 text-brand-700">${icon(iconId, "icon")}</span>${label}</dt><dd class="font-semibold break-words">${value}</dd></div>` : "";
  const coordinator = c.coordinator_name ? `${esc(c.coordinator_name)}${c.coordinator_email ? `<br><a class="font-normal text-brand-700 hover:underline" href="mailto:${esc(c.coordinator_email)}">${esc(c.coordinator_email)}</a>` : ""}` : "";
  body.innerHTML = `<div class="grid gap-12 lg:grid-cols-[1fr_22rem] lg:gap-16">
    <div class="min-w-0 max-w-[46rem]">
      ${c.photo ? `<div class="photo mb-8 aspect-[16/9] rounded-sm"><img src="${esc(c.photo)}" alt="${esc(c.photo_alt)}"></div>` : ""}
      <div class="space-y-5 text-[1.125rem] leading-relaxed text-ink-2">${paragraphs(c.about)}</div>
      ${data.committee.length ? `<section class="mt-12" aria-labelledby="committee-title">
        <h2 id="committee-title" class="font-serif text-h3 font-semibold">Committee</h2>
        <ul class="mt-4 grid gap-3 sm:grid-cols-2">${data.committee.map((m) => `<li class="rounded-sm border border-line px-4 py-3"><p class="font-semibold">${esc(m.name)}</p><p class="text-[0.9375rem] text-ink-2">${esc(m.position)}</p></li>`).join("")}</ul>
      </section>` : ""}
      <section class="mt-12" aria-labelledby="activities-title">
        <h2 id="activities-title" class="font-serif text-h3 font-semibold">Activities</h2>
        ${data.activities.length ? `<ul class="mt-6 space-y-8">${data.activities.map((a) => activityItem(a, { showClub: false })).join("")}</ul>` : `<p class="mt-3 text-ink-2">Activities will appear here as the club posts them.</p>`}
      </section>
      <p class="mt-12 border-t border-line pt-6"><a class="link-arrow" href="/clubs">${icon("chevron-left")} All clubs</a></p>
    </div>
    <aside class="lg:sticky lg:top-28 lg:self-start" aria-label="Club details">
      <div class="rounded-sm border border-line bg-white p-6">
        <dl class="divided">
          ${fact("clock", "Meets", esc(c.meeting_info))}
          ${fact("user", "Staff coordinator", coordinator)}
          ${fact("users", "Members", String(c.member_count))}
        </dl>
        <div class="mt-4 border-t border-line pt-5" data-join aria-live="polite"></div>
      </div>
    </aside>
  </div>`;
  initPhotos(body);
  joinPanel(c, preview);
}

async function joinPanel(c, preview) {
  const box = $("[data-join]");
  if (preview) { box.innerHTML = `<button class="btn btn-primary w-full" disabled>Ask to join</button><p class="mt-2 text-[0.875rem] text-ink-3">Joining works once the clubs service is running.</p>`; return; }
  const mine = await session(`eca/me/clubs/${encodeURIComponent(c.slug)}`);
  const m = mine.body?.membership;
  if (m) {
    const approved = m.status === "approved";
    box.innerHTML = `<p class="flex items-center gap-2 font-semibold ${approved ? "text-leaf-700" : "text-amber-700"}">${icon(approved ? "check" : "clock", "icon")}${approved ? `You're a member${m.position ? ` · ${esc(m.position)}` : ""}` : "Request sent"}</p>
      <p class="mt-1 text-[0.9375rem] text-ink-2">${approved ? "Welcome aboard." : "The ECA team will review it. Check back here or under My activity in your dashboard."}</p>
      <button type="button" class="btn btn-outline btn-sm mt-4" data-leave>${approved ? "Leave the club" : "Withdraw my request"}</button>
      <p class="mt-2 text-[0.875rem] text-om-700" data-msg></p>`;
    const btn = $("[data-leave]", box);
    btn.addEventListener("click", async () => {
      if (!btn.dataset.armed) { btn.dataset.armed = "1"; btn.textContent = "Click again to confirm"; return; }
      btn.disabled = true;
      const res = await session(`eca/me/clubs/${encodeURIComponent(c.slug)}/join`, { method: "DELETE" });
      if (res.ok) joinPanel(c, false);
      else { $("[data-msg]", box).textContent = res.body?.error?.message || "That didn't work. Try again."; btn.disabled = false; }
    });
    return;
  }
  if (!c.join_open) { box.innerHTML = `<p class="font-semibold">Not taking new members right now.</p><p class="mt-1 text-ink-2">Ask the staff coordinator when the next intake opens.</p>`; return; }
  if (!mine.ok) {
    box.innerHTML = `<a class="btn btn-primary w-full" href="${loginUrl()}">${icon("log-in")}Sign in to join</a><p class="mt-2 text-[0.875rem] text-ink-3">Use your @ncit.edu.np account.</p>`;
    return;
  }
  box.innerHTML = `<form data-join-form>
    <label for="join-msg" class="field-label">Why do you want to join? <span class="font-normal text-ink-3">(optional)</span></label>
    <textarea id="join-msg" class="field min-h-24" maxlength="500" placeholder="Your year, programme, what you'd like to do"></textarea>
    <button type="submit" class="btn btn-primary mt-3 w-full">Ask to join</button>
    <p class="mt-2 text-[0.875rem] text-om-700" data-msg></p>
  </form>`;
  $("[data-join-form]", box).addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const btn = $("button", box);
    btn.disabled = true;
    const res = await session(`eca/me/clubs/${encodeURIComponent(c.slug)}/join`, { method: "POST", json: { message: $("#join-msg").value } });
    if (res.ok) { joinPanel(c, false); return; }
    $("[data-msg]", box).textContent = res.body?.error?.message || "That didn't work. Try again.";
    btn.disabled = false;
  });
}

/* ---------- route ---------- */

const eventSlug = location.pathname.match(/^\/events\/([a-z0-9-]+)\/?$/)?.[1] || params.get("e");
const clubSlug = location.pathname.match(/^\/clubs\/([a-z0-9-]+)\/?$/)?.[1] || params.get("c");
if (page === "events") eventsPage();
if (page === "event") eventSlug ? eventPage(eventSlug) : location.replace("/events");
if (page === "clubs") clubsPage();
if (page === "club") clubSlug ? clubPage(clubSlug) : location.replace("/clubs");
