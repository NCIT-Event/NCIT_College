// Shared by the Events and Clubs pages and the home page.
// Reads come from event-service (/api/v1/events/public/...) and eca-service
// (/api/v1/eca/public/...). With no backend (static preview), bundled preview
// data is used and labelled. Signing up for events and clubs needs a session.

export { esc, icon, paragraphs } from "./content-shared.js";

const NPT = 345; // Nepal is UTC+05:45; event times are shown in Nepal time wherever the visitor is
const npt = (iso) => new Date(new Date(iso).getTime() + NPT * 60000);
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const LONG_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const pad = (n) => String(n).padStart(2, "0");

export const nepal = {
  day: (iso) => npt(iso).getUTCDate(),
  month: (iso) => MONTHS[npt(iso).getUTCMonth()],
  key: (iso) => { const d = npt(iso); return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}`; },
  time: (iso) => { const d = npt(iso); return `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`; },
  date: (iso) => { const d = npt(iso); return `${DAYS[d.getUTCDay()]} ${d.getUTCDate()} ${LONG_MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}`; },
  shortDate: (iso) => { const d = npt(iso); return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}`; },
  monthName: (ym) => { const [y, m] = ym.split("-").map(Number); return `${LONG_MONTHS[m - 1]} ${y}`; },
  thisMonth: () => nepal.key(new Date().toISOString()).slice(0, 7),
};

/** "12–14 Dec · 09:00" style summary of when an event happens (Nepal time). */
export function when(e) {
  const sameDay = !e.end_at || nepal.key(e.start_at) === nepal.key(e.end_at);
  if (sameDay) return `${nepal.date(e.start_at)} · ${nepal.time(e.start_at)}${e.end_at ? `–${nepal.time(e.end_at)}` : ""}`;
  return `${nepal.shortDate(e.start_at)} – ${nepal.date(e.end_at)}`;
}

export const EVENT_CATEGORIES = { academic: "Academic", technical: "Technical", workshop: "Workshop", seminar: "Seminar",
  cultural: "Cultural", sports: "Sports", career: "Career", general: "General" };
export const CLUB_CATEGORIES = { technical: "Technical", cultural: "Cultural", sports: "Sports", arts: "Arts", social: "Social", academic: "Academic" };

/* ---------- public reads, with preview fallback ---------- */

let previewCache;
const preview = () => (previewCache ??= fetch("/assets/data/campus-preview.json").then((r) => r.json()).catch(() => null));

function previewAnswer(p, service, path) {
  const [base, query] = path.split("?");
  const q = new URLSearchParams(query || "");
  const now = Date.now();
  const list = (items) => ({ items, total: items.length, page: 1, per_page: 50 });
  if (service === "events") {
    const ends = (e) => new Date(e.end_at || new Date(new Date(e.start_at).getTime() + 3 * 3600e3)).getTime();
    const cat = q.get("category");
    const pool = p.events.filter((e) => !cat || e.category === cat);
    if (base === "events") {
      const past = q.get("when") === "past";
      const items = pool.filter((e) => (ends(e) > now) !== past)
        .sort((a, b) => (past ? -1 : 1) * (new Date(a.start_at) - new Date(b.start_at)));
      return list(items.slice(0, Number(q.get("limit") || 50)));
    }
    if (base === "calendar") {
      const month = q.get("month") || nepal.thisMonth();
      return { month, items: p.events.filter((e) => nepal.key(e.start_at).startsWith(month)) };
    }
    if (base.startsWith("events/")) {
      const event = p.events.find((e) => e.slug === base.slice(7));
      return event ? { event } : null;
    }
  }
  if (service === "eca") {
    if (base === "clubs") return { items: p.clubs.filter((c) => !q.get("category") || c.category === q.get("category")) };
    if (base === "activities") return { items: p.activities.slice(0, Number(q.get("limit") || 6)) };
    if (base.startsWith("clubs/")) {
      const club = p.clubs.find((c) => c.slug === base.slice(6));
      return club ? { club, committee: [], activities: p.activities.filter((a) => a.club?.slug === club.slug) } : null;
    }
  }
  return null;
}

/** GET /api/v1/<service>/public/<path>. Returns { data, status, preview }. */
export async function loadPublic(service, path) {
  try {
    const res = await fetch(`/api/v1/${service}/public/${path}`, { headers: { Accept: "application/json" } });
    const json = (res.headers.get("content-type") || "").includes("json");
    if (json && (res.ok || res.status === 404)) return { data: res.ok ? await res.json() : null, status: res.status };
  } catch { /* fall back to preview data */ }
  const p = await preview();
  if (!p) return { data: null, status: 0 };
  const data = previewAnswer(p, service, path);
  return { data, status: data ? 200 : 404, preview: true };
}

/* ---------- signed-in actions ---------- */

const csrf = () => document.cookie.split("; ").find((c) => c.startsWith("ncit_csrf="))?.split("=")[1] || "";
let refreshing = null;

/** Call a signed-in endpoint; refreshes an expired session once. Returns { ok, status, body }. */
export async function session(path, { method = "GET", json } = {}, retried = false) {
  const headers = { Accept: "application/json" };
  if (method !== "GET") headers["X-CSRF-Token"] = csrf();
  if (json !== undefined) headers["Content-Type"] = "application/json";
  let res;
  try {
    res = await fetch(`/api/v1/${path}`, { method, headers, credentials: "same-origin", body: json === undefined ? undefined : JSON.stringify(json) });
  } catch { return { ok: false, status: 0, body: null }; }
  const body = (res.headers.get("content-type") || "").includes("json") ? await res.json().catch(() => null) : null;
  if (res.status === 401 && !retried && csrf()) {
    refreshing ??= fetch("/api/v1/auth/refresh", { method: "POST", credentials: "same-origin", headers: { "X-CSRF-Token": csrf() } })
      .then((r) => r.ok).catch(() => false).finally(() => { refreshing = null; });
    if (await refreshing) return session(path, { method, json }, true);
  }
  return { ok: res.ok, status: res.status, body };
}

export const loginUrl = () => `/login.html?next=${encodeURIComponent(location.pathname)}`;
