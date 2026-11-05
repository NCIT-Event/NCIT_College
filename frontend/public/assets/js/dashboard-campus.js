// Campus life in the dashboard, beyond plain editing (which dashboard-content.js does):
// - Event Admins: who registered for an event, attendance, waiting list, CSV export.
// - ECA Admins: club members and join requests (approve, reject, committee positions).
// - Everyone: My activity (my event registrations and club memberships).

let ctx; // { api, toast, toastError, esc, icon, drawers, reload }
const $ = (sel, root = document) => root.querySelector(sel);
const sheet = () => document.getElementById("people-sheet");
// shown in Nepal time (UTC+05:45) whatever the computer's time zone
const MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const npt = (iso) => new Date(new Date(iso).getTime() + 345 * 60000);
const pad = (n) => String(n).padStart(2, "0");
const day = (iso) => { if (!iso) return ""; const d = npt(iso); return `${d.getUTCDate()} ${MON[d.getUTCMonth()]} ${d.getUTCFullYear()}`; };
const fmt = (iso) => { if (!iso) return ""; const d = npt(iso); return `${day(iso)}, ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`; };

const REG_TAG = { registered: ["tag-leaf", "Registered"], waitlisted: ["tag-amber", "Waiting list"], cancelled: ["", "Cancelled"] };
const MEMBER_TAG = { pending: ["tag-amber", "Waiting"], approved: ["tag-leaf", "Member"], rejected: ["tag-om", "Not accepted"], left: ["", "Left"] };

let current = null; // { type: "event" | "club", item }

function person(x) {
  const { esc } = ctx;
  return `<p class="font-semibold">${esc(x.name || x.email)}</p><p class="truncate text-[0.9375rem] text-ink-2"><a class="hover:text-brand-700 hover:underline" href="mailto:${esc(x.email)}">${esc(x.email)}</a></p>`;
}

/* ---------- event registrations ---------- */

async function openRegistrations(event) {
  current = { type: "event", item: event };
  const { esc, icon } = ctx;
  $("[data-people-title]").textContent = "Registrations";
  $("[data-people-sub]").textContent = event.title;
  $("[data-people-tools]").innerHTML = `<a class="btn btn-outline btn-sm" href="/api/v1/events/events/${esc(event.id)}/registrations.csv" download>${icon("download")}Download CSV</a>
    <p class="text-[0.875rem] text-ink-3" data-people-count></p>`;
  $("[data-people-list]").innerHTML = `<li class="px-5 py-8 text-center text-ink-2">Loading…</li>`;
  ctx.drawers.setOpen(sheet(), true);
  await loadRegistrations();
}

async function loadRegistrations() {
  const { esc, icon } = ctx;
  const event = current.item;
  try {
    const data = await ctx.api(`/events/events/${event.id}/registrations`);
    const n = (s) => data.items.filter((r) => r.status === s).length;
    $("[data-people-count]").textContent = `${n("registered")}${data.event.capacity ? ` of ${data.event.capacity}` : ""} registered · ${n("waitlisted")} waiting · ${data.items.filter((r) => r.attended).length} attended`;
    $("[data-people-list]").innerHTML = data.items.length ? data.items.map((r) => {
      const [cls, label] = REG_TAG[r.status] || ["", r.status];
      const actions = r.status === "cancelled"
        ? `<button type="button" class="btn btn-ghost btn-sm" data-reg="${esc(r.id)}" data-set="registered">Restore</button>`
        : `${r.status === "waitlisted" ? `<button type="button" class="btn btn-ghost btn-sm" data-reg="${esc(r.id)}" data-set="registered" title="Admit even if the event is full">Admit</button>` : ""}
           <button type="button" class="btn btn-ghost btn-sm text-om-700 hover:bg-om-50 hover:text-om-700" data-reg="${esc(r.id)}" data-set="cancelled">Cancel</button>`;
      return `<li class="flex flex-wrap items-center gap-x-4 gap-y-2 px-5 py-3.5">
        <div class="min-w-0 flex-1 basis-[14rem]">${person(r)}
          <p class="text-[0.875rem] text-ink-3"><span class="tag ${cls} mr-1.5">${label}${r.waitlist_position ? ` #${r.waitlist_position}` : ""}</span>${esc(fmt(r.created_at))}</p></div>
        <label class="inline-flex min-h-11 cursor-pointer items-center gap-2 text-[0.9375rem] font-semibold ${r.status === "registered" ? "" : "invisible"}"><input type="checkbox" class="h-5 w-5 accent-brand-700" data-attend="${esc(r.id)}" ${r.attended ? "checked" : ""}>Attended</label>
        <div class="flex gap-1">${actions}</div>
      </li>`;
    }).join("") : `<li class="px-5 py-10 text-center text-ink-2">${icon("users", "icon mx-auto mb-2 text-ink-3")}No one has registered yet.</li>`;
  } catch (err) { if (err.status !== 401) ctx.toastError(err); }
}

async function updateRegistration(id, json) {
  try {
    await ctx.api(`/events/events/${current.item.id}/registrations/${id}`, { method: "PATCH", json });
    await loadRegistrations();
    ctx.reload();
  } catch (err) { ctx.toastError(err); }
}

/* ---------- club members ---------- */

async function openMembers(club) {
  current = { type: "club", item: club };
  $("[data-people-title]").textContent = "Members";
  $("[data-people-sub]").textContent = club.name;
  $("[data-people-tools]").innerHTML = `<p class="text-[0.875rem] text-ink-3" data-people-count></p>`;
  $("[data-people-list]").innerHTML = `<li class="px-5 py-8 text-center text-ink-2">Loading…</li>`;
  ctx.drawers.setOpen(sheet(), true);
  await loadMembers();
}

function decisionButtons(m, clubId) {
  const { esc } = ctx;
  const b = (status, label, danger = false) => `<button type="button" class="btn btn-ghost btn-sm ${danger ? "text-om-700 hover:bg-om-50 hover:text-om-700" : ""}" data-member="${esc(m.id)}" data-club="${esc(clubId)}" data-set="${status}">${label}</button>`;
  if (m.status === "pending") return b("approved", "Approve") + b("rejected", "Reject", true);
  if (m.status === "approved") return b("left", "Remove", true);
  return b("approved", "Approve");
}

async function loadMembers() {
  const { esc, icon } = ctx;
  const club = current.item;
  try {
    const data = await ctx.api(`/eca/clubs/${club.id}/members`);
    const n = (s) => data.items.filter((m) => m.status === s).length;
    $("[data-people-count]").textContent = `${n("approved")} member${n("approved") === 1 ? "" : "s"} · ${n("pending")} waiting for a decision`;
    $("[data-people-list]").innerHTML = data.items.length ? data.items.map((m) => {
      const [cls, label] = MEMBER_TAG[m.status] || ["", m.status];
      return `<li class="px-5 py-3.5">
        <div class="flex flex-wrap items-start gap-x-4 gap-y-2">
          <div class="min-w-0 flex-1 basis-[14rem]">${person(m)}
            <p class="text-[0.875rem] text-ink-3"><span class="tag ${cls} mr-1.5">${label}</span>asked ${esc(day(m.created_at))}${m.decided_by ? ` · decided by ${esc(m.decided_by)}` : ""}</p></div>
          <div class="flex gap-1">${decisionButtons(m, club.id)}</div>
        </div>
        ${m.message ? `<p class="mt-2 rounded-sm bg-canvas px-3 py-2 text-[0.9375rem] text-ink-2">“${esc(m.message)}”</p>` : ""}
        ${m.status === "approved" ? `<form class="mt-2 flex flex-wrap items-center gap-2" data-position="${esc(m.id)}">
          <label class="text-[0.875rem] text-ink-3" for="pos-${esc(m.id)}">Committee position</label>
          <input id="pos-${esc(m.id)}" class="field h-9 min-h-0 w-auto flex-1 basis-[10rem] py-1" maxlength="60" placeholder="e.g. President (empty = member)" value="${esc(m.position)}">
          <button class="btn btn-outline btn-sm" type="submit">Save</button>
        </form>` : ""}
      </li>`;
    }).join("") : `<li class="px-5 py-10 text-center text-ink-2">${icon("users", "icon mx-auto mb-2 text-ink-3")}No members or requests yet.</li>`;
  } catch (err) { if (err.status !== 401) ctx.toastError(err); }
}

async function decide(clubId, memberId, json, after) {
  try {
    const { item } = await ctx.api(`/eca/clubs/${clubId}/members/${memberId}`, { method: "PATCH", json });
    const verb = { approved: "approved", rejected: "not accepted", left: "removed" }[json.status];
    ctx.toast(`${ctx.icon("check")}<span>${ctx.esc(item.name || item.email)} ${verb ? verb : "updated"}.</span>`);
    await after();
    refreshBadge();
  } catch (err) { ctx.toastError(err); }
}

/* ---------- join requests view ---------- */

export async function showRequests() {
  const { esc, icon } = ctx;
  const list = $("[data-requests-list]");
  list.innerHTML = `<li class="px-5 py-8 text-center text-ink-2">Loading…</li>`;
  try {
    const { items } = await ctx.api("/eca/requests/pending");
    setBadge(items.length);
    list.innerHTML = items.length ? items.map((m) => `<li class="px-5 py-4">
      <div class="flex flex-wrap items-start gap-x-4 gap-y-2">
        <div class="min-w-0 flex-1 basis-[14rem]">${person(m)}
          <p class="text-[0.875rem] text-ink-3">wants to join <a class="font-semibold text-brand-700 hover:underline" href="/clubs/${esc(m.club.slug)}" target="_blank" rel="noopener">${esc(m.club.name)}</a> · ${esc(day(m.created_at))}</p></div>
        <div class="flex gap-1">${decisionButtons(m, m.club.id)}</div>
      </div>
      ${m.message ? `<p class="mt-2 rounded-sm bg-canvas px-3 py-2 text-[0.9375rem] text-ink-2">“${esc(m.message)}”</p>` : ""}
    </li>`).join("") : `<li class="px-5 py-10 text-center text-ink-2">${icon("inbox", "icon mx-auto mb-2 text-ink-3")}No requests waiting. New ones appear here.</li>`;
  } catch (err) { if (err.status !== 401) ctx.toastError(err); }
}

function setBadge(n) {
  const badge = $("[data-requests-badge]");
  if (!badge) return;
  badge.textContent = n;
  badge.classList.toggle("hidden", !n);
}

export async function refreshBadge() {
  try { setBadge((await ctx.api("/eca/requests/pending")).items.length); } catch { /* not an ECA Admin, or offline */ }
}

/* ---------- my activity ---------- */

export async function showMine() {
  const { esc, icon } = ctx;
  const evList = $("[data-mine-events]");
  const clubList = $("[data-mine-clubs]");
  evList.innerHTML = clubList.innerHTML = `<li class="px-5 py-6 text-ink-2">Loading…</li>`;
  const [events, clubs] = await Promise.all([
    ctx.api("/events/me/registrations").catch(() => null),
    ctx.api("/eca/me/memberships").catch(() => null),
  ]);
  const now = Date.now();
  evList.innerHTML = !events ? `<li class="px-5 py-6 text-ink-2">Your registrations couldn't be loaded.</li>`
    : events.items.length ? events.items.map((r) => {
      const past = new Date(r.event.end_at || r.event.start_at) < now;
      const [cls, label] = past ? ["", r.attended ? "Attended" : "Past"] : REG_TAG[r.status];
      return `<li class="flex flex-wrap items-center gap-4 px-5 py-3.5">
        <div class="min-w-0 flex-1 basis-[14rem]"><p class="font-semibold"><a class="hover:text-brand-700" href="/events/${esc(r.event.slug)}">${esc(r.event.title)}</a></p>
          <p class="text-[0.9375rem] text-ink-2">${esc(fmt(r.event.start_at))}${r.event.venue ? ` · ${esc(r.event.venue)}` : ""}</p></div>
        <span class="tag ${cls}">${label}${!past && r.waitlist_position ? ` #${r.waitlist_position}` : ""}</span>
      </li>`;
    }).join("") : `<li class="px-5 py-6 text-ink-2">${icon("calendar", "icon-sm mr-1 inline align-[-0.15em]")}No registrations yet. <a class="font-semibold text-brand-700 hover:underline" href="/events">See upcoming events</a></li>`;
  clubList.innerHTML = !clubs ? `<li class="px-5 py-6 text-ink-2">Your clubs couldn't be loaded.</li>`
    : clubs.items.length ? clubs.items.map((m) => {
      const [cls, label] = MEMBER_TAG[m.status];
      return `<li class="flex flex-wrap items-center gap-4 px-5 py-3.5">
        <div class="min-w-0 flex-1 basis-[14rem]"><p class="font-semibold"><a class="hover:text-brand-700" href="/clubs/${esc(m.club.slug)}">${esc(m.club.name)}</a></p>
          <p class="text-[0.9375rem] text-ink-2">${m.position ? esc(m.position) : m.status === "pending" ? "Waiting for the ECA team" : esc(m.club.meeting_info || "")}</p></div>
        <span class="tag ${cls}">${label}</span>
      </li>`;
    }).join("") : `<li class="px-5 py-6 text-ink-2">${icon("trophy", "icon-sm mr-1 inline align-[-0.15em]")}Not in a club yet. <a class="font-semibold text-brand-700 hover:underline" href="/clubs">Find a club</a></li>`;
}

/* ---------- wiring ---------- */

export function campusAction(action, item) {
  if (action === "registrations") openRegistrations(item);
  if (action === "members") openMembers(item);
  if (action === "intake-applications") location.hash = `applications/${item.id}`;
  if (action === "job-applications") location.hash = `job-applications/${item.id}`;
}

export function initCampus(context) {
  ctx = context;
  document.addEventListener("click", (e) => {
    const reg = e.target.closest("[data-reg]");
    if (reg) {
      if (reg.dataset.set === "cancelled" && reg.dataset.armed !== "1") {
        reg.dataset.armed = "1";
        reg.textContent = "Really cancel?";
        setTimeout(() => { reg.dataset.armed = ""; reg.textContent = "Cancel"; }, 4000);
        return;
      }
      updateRegistration(reg.dataset.reg, { status: reg.dataset.set });
      return;
    }
    const mem = e.target.closest("[data-member]");
    if (mem) {
      const inSheet = mem.closest("#people-sheet");
      decide(mem.dataset.club, mem.dataset.member, { status: mem.dataset.set }, inSheet ? async () => { await loadMembers(); ctx.reload(); } : showRequests);
    }
  });
  document.addEventListener("change", (e) => {
    const box = e.target.closest("[data-attend]");
    if (box) updateRegistration(box.dataset.attend, { attended: box.checked });
  });
  document.addEventListener("submit", (e) => {
    const form = e.target.closest("[data-position]");
    if (!form) return;
    e.preventDefault();
    decide(current.item.id, form.dataset.position, { position: form.querySelector("input").value.trim() }, loadMembers);
  });
}
