// The bell: in-app notifications for whoever is signed in, in the website header and the dashboard.
// Loaded only when a session cookie is present (see site.js), and it stays hidden unless
// notification-service confirms a signed-in user. Unread count is checked every minute while the
// tab is visible, and straight away when you come back to the tab.

const API = "/api/v1/notify/me/notifications";
const ICONS = "/assets/img/icons.svg";
const POLL_MS = 60_000;
const PER_PAGE = 8;

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const icon = (id, cls = "icon-sm") => `<svg class="${cls}" aria-hidden="true"><use href="${ICONS}#i-${id}"/></svg>`;
const csrf = () => document.cookie.split("; ").find((c) => c.startsWith("ncit_csrf="))?.split("=")[1] || "";
const safeLink = (l) => (typeof l === "string" && /^\/(?![/\\])[^\s\\]*$/.test(l) ? l : "");

const KIND = {
  success: { icon: "check", cls: "bg-leaf-50 text-leaf-700" },
  warning: { icon: "circle-alert", cls: "bg-om-50 text-om-700" },
  action: { icon: "inbox", cls: "bg-amber-50 text-amber-700" },
  info: { icon: "bell", cls: "bg-brand-50 text-brand-700" },
};

const rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
function ago(iso) {
  const secs = (new Date(iso) - Date.now()) / 1000;
  for (const [unit, size] of [["year", 31536000], ["month", 2592000], ["week", 604800], ["day", 86400], ["hour", 3600], ["minute", 60]]) {
    if (Math.abs(secs) >= size) return rtf.format(Math.round(secs / size), unit);
  }
  return "just now";
}

async function call(path = "", { method = "GET", json, retried = false } = {}) {
  const headers = { Accept: "application/json" };
  if (method !== "GET") { headers["X-CSRF-Token"] = csrf(); headers["Content-Type"] = "application/json"; }
  const res = await fetch(API + path, { method, headers, credentials: "same-origin", body: json ? JSON.stringify(json) : undefined, keepalive: method !== "GET" });
  if (res.status === 401 && !retried) {
    // the 15-minute access token ran out: renew it once with the refresh cookie
    const r = await fetch("/api/v1/auth/refresh", { method: "POST", credentials: "same-origin", headers: { "X-CSRF-Token": csrf() } });
    if (r.ok) return call(path, { method, json, retried: true });
  }
  if (!res.ok) throw Object.assign(new Error(`HTTP ${res.status}`), { status: res.status });
  return res.json();
}

function mount(slot) {
  const id = `bell-panel-${Math.random().toString(36).slice(2, 8)}`;
  const onDark = slot.dataset.bell === "dark";
  slot.innerHTML = `
    <button type="button" class="btn btn-ghost relative h-11 w-11 px-0 ${onDark ? "text-white hover:bg-white/10" : ""}" aria-haspopup="dialog" aria-expanded="false" aria-controls="${id}" data-bell-button>
      ${icon("bell", "icon")}
      <span class="absolute top-1.5 right-1.5 hidden min-w-[1.125rem] rounded-full bg-om-600 px-1 text-center text-[0.6875rem] leading-[1.125rem] font-semibold text-white" data-bell-badge></span>
    </button>
    <div id="${id}" role="dialog" aria-label="Notifications" hidden data-bell-panel
         class="fixed inset-x-2 top-[4.75rem] z-[90] max-h-[min(36rem,calc(100svh-6rem))] overflow-hidden rounded-md border border-line bg-white text-ink shadow-xl sm:absolute sm:inset-x-auto sm:top-full sm:right-0 sm:mt-2 sm:w-[24rem]">
      <div class="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
        <h2 class="font-semibold">Notifications</h2>
        <button type="button" class="text-[0.875rem] font-semibold text-brand-700 hover:underline disabled:text-ink-3 disabled:no-underline" data-bell-all>Mark all as read</button>
      </div>
      <ul class="max-h-[28rem] divide-y divide-line-2 overflow-y-auto" data-bell-list aria-live="polite"></ul>
      <div class="border-t border-line px-4 py-2 text-center" data-bell-more hidden>
        <button type="button" class="text-[0.875rem] font-semibold text-brand-700 hover:underline" data-bell-older>Show older</button>
      </div>
    </div>`;
  const button = slot.querySelector("[data-bell-button]");
  const badge = slot.querySelector("[data-bell-badge]");
  const panel = slot.querySelector("[data-bell-panel]");
  const list = slot.querySelector("[data-bell-list]");
  const more = slot.querySelector("[data-bell-more]");
  const allBtn = slot.querySelector("[data-bell-all]");
  let page = 1, items = [], timer = null;

  const setUnread = (n) => {
    badge.textContent = n > 99 ? "99+" : String(n);
    badge.classList.toggle("hidden", !n);
    button.setAttribute("aria-label", n ? `Notifications, ${n} unread` : "Notifications");
    allBtn.disabled = !n;
  };

  const row = (n) => {
    const k = KIND[n.kind] || KIND.info;
    const link = safeLink(n.link);
    const inner = `
      <span class="mt-0.5 flex h-8 w-8 flex-none items-center justify-center rounded-full ${k.cls}">${icon(k.icon)}</span>
      <span class="min-w-0 flex-1">
        <span class="block text-[0.9375rem] ${n.read ? "text-ink-2" : "font-semibold"}">${esc(n.title)}</span>
        ${n.body ? `<span class="mt-0.5 line-clamp-2 block text-[0.875rem] text-ink-2">${esc(n.body)}</span>` : ""}
        <span class="mt-1 block text-[0.8125rem] text-ink-3">${esc(ago(n.created_at))}${n.for_role ? " · for your role" : ""}</span>
      </span>
      ${n.read ? "" : `<span class="mt-2 h-2.5 w-2.5 flex-none rounded-full bg-om-600"><span class="sr-only">Unread</span></span>`}`;
    const cls = "flex gap-3 px-4 py-3 text-left hover:bg-canvas focus-visible:bg-canvas";
    return `<li>${link
      ? `<a class="${cls}" href="${esc(link)}" data-note="${esc(n.id)}">${inner}</a>`
      : `<button type="button" class="${cls} w-full" data-note="${esc(n.id)}">${inner}</button>`}</li>`;
  };

  const render = () => {
    list.innerHTML = items.length ? items.map(row).join("")
      : `<li class="px-4 py-10 text-center text-[0.9375rem] text-ink-2">${icon("bell", "icon mx-auto mb-2 text-ink-3")}You're all caught up.</li>`;
  };

  async function refreshCount() {
    try {
      setUnread((await call("/unread")).unread);
      return true;
    } catch (err) {
      if (err.status === 401) { stop(); slot.hidden = true; }  // signed out elsewhere
      return false;
    }
  }

  async function load(next = false) {
    page = next ? page + 1 : 1;
    if (!next) list.innerHTML = `<li class="px-4 py-6 text-center text-[0.9375rem] text-ink-2">Loading…</li>`;
    try {
      const data = await call(`?page=${page}&per_page=${PER_PAGE}`);
      items = next ? [...items, ...data.items] : data.items;
      more.hidden = !data.more;
      setUnread(data.unread);
      render();
    } catch {
      list.innerHTML = `<li class="px-4 py-6 text-center text-[0.9375rem] text-ink-2">Notifications couldn't be loaded. Try again in a minute.</li>`;
    }
  }

  async function markRead(ids) {
    try { setUnread((await call("/read", { method: "POST", json: ids ? { ids } : { all: true } })).unread); } catch { /* next poll corrects it */ }
  }

  const isOpen = () => !panel.hidden;
  function open() {
    panel.hidden = false;
    button.setAttribute("aria-expanded", "true");
    load();
    requestAnimationFrame(() => allBtn.disabled ? panel.querySelector("[data-note], button")?.focus() : allBtn.focus());
  }
  function close(focusButton = false) {
    panel.hidden = true;
    button.setAttribute("aria-expanded", "false");
    if (focusButton) button.focus();
  }

  button.addEventListener("click", () => (isOpen() ? close() : open()));
  allBtn.addEventListener("click", async () => {
    items = items.map((n) => ({ ...n, read: true }));
    render();
    await markRead(null);
  });
  slot.querySelector("[data-bell-older]").addEventListener("click", () => load(true));
  list.addEventListener("click", (e) => {
    const el = e.target.closest("[data-note]");
    if (!el) return;
    const n = items.find((x) => x.id === el.dataset.note);
    if (n && !n.read) { n.read = true; markRead([n.id]); render(); }
    if (el.tagName === "A") close();
  });
  document.addEventListener("click", (e) => { if (isOpen() && !slot.contains(e.target)) close(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && isOpen()) close(true); });

  const start = () => { stop(); timer = setInterval(() => document.visibilityState === "visible" && refreshCount(), POLL_MS); };
  function stop() { clearInterval(timer); timer = null; }
  document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible" && timer) refreshCount(); });

  refreshCount().then((ok) => { if (ok) { slot.hidden = false; start(); } });
}

export function mountAll() {
  document.querySelectorAll("[data-bell]").forEach((slot) => { if (!slot.dataset.bellMounted) { slot.dataset.bellMounted = "1"; mount(slot); } });
}
