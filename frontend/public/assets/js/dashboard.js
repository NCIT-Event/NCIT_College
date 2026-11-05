// Dashboard: signed-in user, role-based menu, Users & access, Audit log.
// Talks to auth-service and audit-service through the gateway (/api/v1/...).
// When no backend answers (static preview), a clearly labelled demo backend
// with the same responses takes over, so the screens can still be reviewed.

import { api as site } from "./site.js";
import { demoFetch } from "./dashboard-demo.js";
import { initDepartments, showDepartments } from "./dashboard-departments.js";
import { CONTENT_VIEWS, contentRoles, contentTitle, initContent, reloadContent, showContent } from "./dashboard-content.js";
import { campusAction, initCampus, refreshBadge, showMine, showRequests } from "./dashboard-campus.js";
import { REVIEW_VIEWS, initReview, reviewRoles, reviewTitle, showReview } from "./dashboard-review.js";

const ICONS = "/assets/img/icons.svg";
const API = "/api/v1";

const state = {
  demo: false,
  me: null,
  roles: [],          // role catalogue
  departments: [],
  users: { page: 1, total: 0, perPage: 25 },
  audit: { page: 1, total: 0, perPage: 25 },
};

/* ---------- helpers ---------- */

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const icon = (id, cls = "icon-sm") => `<svg class="${cls}" aria-hidden="true"><use href="${ICONS}#i-${id}"/></svg>`;
const initials = (name) => (name || "?").split(/[\s.@]+/).filter(Boolean).map((w) => w[0]).slice(0, 2).join("").toUpperCase();
const debounce = (fn, ms = 250) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };
const roleName = (code) => state.roles.find((r) => r.code === code)?.name || code;
const myRoles = () => (state.me?.roles || []).map((r) => r.role);
const isSuperAdmin = () => myRoles().includes("super_admin");

const rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
function relative(iso) {
  if (!iso) return "";
  const secs = (new Date(iso) - Date.now()) / 1000;
  const units = [["year", 31536000], ["month", 2592000], ["week", 604800], ["day", 86400], ["hour", 3600], ["minute", 60]];
  for (const [unit, size] of units) if (Math.abs(secs) >= size) return rtf.format(Math.round(secs / size), unit);
  return "just now";
}
const dateTime = (iso) => new Date(iso).toLocaleString("en-GB", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });

function csrfToken() {
  return document.cookie.split("; ").find((c) => c.startsWith("ncit_csrf="))?.split("=")[1] || "";
}

/* ---------- API client ---------- */

class ApiError extends Error {
  constructor(status, code, message) { super(message); this.status = status; this.code = code; }
}

function loginRedirect() {
  const next = encodeURIComponent(location.pathname + location.hash);
  location.assign(`/login.html?next=${next}`);
}

async function rawFetch(path, options = {}) {
  if (state.demo) return demoFetch(path, options);
  const headers = { Accept: "application/json", ...(options.headers || {}) };
  if (options.method && options.method !== "GET") headers["X-CSRF-Token"] = csrfToken();
  if (options.json !== undefined) { headers["Content-Type"] = "application/json"; options.body = JSON.stringify(options.json); }
  return fetch(API + path, { credentials: "same-origin", ...options, headers });
}

let refreshing = null;
async function refreshSession() {
  refreshing ??= rawFetch("/auth/refresh", { method: "POST" }).then((r) => r.ok).finally(() => { refreshing = null; });
  return refreshing;
}

async function api(path, options = {}, retried = false) {
  const res = await rawFetch(path, { ...options });
  let body = null;
  try { body = await res.json(); } catch { /* empty or non-JSON */ }
  if (res.status === 401 && !retried) {
    // expired or revoked access token: get a new one once, then retry
    if (await refreshSession()) return api(path, options, true);
    loginRedirect();
    throw new ApiError(401, "not_signed_in", "Sign in to continue.");
  }
  if (!res.ok) {
    throw new ApiError(res.status, body?.error?.code || "error", body?.error?.message || "Something went wrong. Try again.");
  }
  return body;
}

async function backendAvailable() {
  try {
    const res = await fetch(`${API}/auth/config`, { headers: { Accept: "application/json" } });
    return res.ok && (res.headers.get("content-type") || "").includes("json");
  } catch {
    return false;
  }
}

/* ---------- toast ---------- */

let toastTimer;
function toast(html, { undo } = {}) {
  const el = $("[data-toast]");
  el.innerHTML = html + (undo ? ` <button type="button" class="font-semibold text-sky-300 underline-offset-2 hover:underline" data-undo>Undo</button>` : "");
  el.classList.remove("hidden");
  el.classList.add("flex");
  if (undo) $("[data-undo]", el).addEventListener("click", () => { el.classList.add("hidden"); undo(); }, { once: true });
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.classList.add("hidden"); el.classList.remove("flex"); }, 7000);
}
const toastError = (err) => toast(`${icon("circle-alert")}<span>${esc(err.message)}</span>`);

/* ---------- shell: user, menu, views ---------- */

function renderShell() {
  const me = state.me;
  $("[data-user-name]").textContent = me.name;
  $("[data-user-email]").textContent = me.email;
  $("[data-user-initials]").textContent = initials(me.name);
  $$("[data-demo-only], [data-demo-banner]").forEach((el) => (el.hidden = !state.demo));
  filterMenu(myRoles());
}

function filterMenu(roles) {
  $$("#dash-nav [data-roles]").forEach((el) => {
    const allowed = el.dataset.roles.split(" ");
    el.hidden = !(allowed.includes("*") || allowed.some((r) => roles.includes(r)));
  });
  // hide group headings whose links are all hidden
  $$("#dash-nav [data-group]").forEach((heading) => {
    let n = heading.nextElementSibling, any = false;
    while (n && !n.matches("[data-group]")) { if (n.matches("a") && !n.hidden) any = true; n = n.nextElementSibling; }
    heading.hidden = !any;
  });
}

const canEditDepartments = () => myRoles().some((r) => r === "super_admin" || r === "hod");
const hasAny = (roles) => () => myRoles().some((r) => roles.includes(r));
const VIEWS = { overview: () => true, mine: () => true, users: isSuperAdmin, audit: isSuperAdmin, departments: canEditDepartments,
  requests: hasAny(["super_admin", "eca_admin"]),
  ...Object.fromEntries(CONTENT_VIEWS.map((v) => [v, hasAny(contentRoles(v))])),
  ...Object.fromEntries(REVIEW_VIEWS.map((v) => [v, hasAny(reviewRoles(v))])) };
const TITLES = { overview: "Overview", users: "Users & access", audit: "Audit log", requests: "Join requests", mine: "My activity" };

function showView() {
  const [hashView, hashArg] = location.hash.slice(1).split("/");
  let view = hashView || "overview";
  if (!VIEWS[view]?.()) view = "overview";
  $("[data-loading]").hidden = true;
  const section = CONTENT_VIEWS.includes(view) ? "content" : REVIEW_VIEWS.includes(view) ? "review" : view;
  $$("[data-view]").forEach((el) => (el.hidden = el.dataset.view !== section));
  $$("[data-view-link]").forEach((a) => {
    if (a.dataset.viewLink === view) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  });
  document.title = `${(view === "departments" ? (isSuperAdmin() ? "Departments" : "My department") : TITLES[view]) || reviewTitle(view) || contentTitle(view)} · NCIT Dashboard`;
  // leaving a section closes anything opened from it
  ["dash-nav", "people-sheet", "content-sheet", "item-sheet", "review-sheet"].forEach((sheet) => {
    const el = document.getElementById(sheet);
    if (el?.dataset.open === "true") site.drawers.setOpen(el, false);
  });
  if (view === "overview") renderOverview();
  if (view === "users") { loadSummary(); loadUsers(); }
  if (view === "audit") loadAudit();
  if (view === "departments") showDepartments(hashArg);
  if (CONTENT_VIEWS.includes(view)) showContent(view);
  if (REVIEW_VIEWS.includes(view)) showReview(view, hashArg);
  if (view === "requests") showRequests();
  if (view === "mine") showMine();
}

/* ---------- overview ---------- */

const MODULES = [
  { roles: ["super_admin"], name: "Users & access", desc: "Grant and remove roles, invite staff, suspend accounts.", view: "users" },
  { roles: ["super_admin"], name: "Audit log", desc: "Every sign-in and access change.", view: "audit" },
  { roles: ["super_admin", "content_admin"], name: "Banners & ads", desc: "Home page banner slides, with start and end dates.", view: "banners" },
  { roles: ["super_admin", "content_admin"], name: "Leadership messages", desc: "Executive Director, Director and Principal.", view: "leadership" },
  { roles: ["super_admin", "content_admin"], name: "News", desc: "Articles for the home page and the News page.", view: "news" },
  { roles: ["super_admin", "content_admin"], name: "Notices", desc: "Exam routines, admissions, holidays and results, with PDFs.", view: "notices" },
  { roles: ["super_admin", "content_admin"], name: "Facilities", view: "facilities" },
  { roles: ["hod"], name: "My department", desc: "Overview, HOD message, programmes, semester courses, faculty, labs and testimonials.", view: "departments" },
  { roles: ["super_admin"], name: "Departments", desc: "Edit any department page, publish or hide it, add new departments.", view: "departments" },
  { roles: ["super_admin", "event_admin"], name: "Events", desc: "The events calendar, registrations, waiting lists and attendance.", view: "events" },
  { roles: ["super_admin", "eca_admin"], name: "Clubs", desc: "Club pages, members and committee positions.", view: "clubs" },
  { roles: ["super_admin", "eca_admin"], name: "Join requests", desc: "Approve or decline students asking to join a club.", view: "requests" },
  { roles: ["super_admin", "eca_admin"], name: "Club activities", desc: "What clubs have been doing, shown on each club page.", view: "activities" },
  { roles: ["super_admin", "admission_officer"], name: "Applications", desc: "Review admission applications and documents; applicants are emailed at every step.", view: "applications" },
  { roles: ["super_admin", "admission_officer"], name: "Intakes and programmes", desc: "Admission rounds, their dates, and the programmes on offer with seats and eligibility.", view: "intakes" },
  { roles: ["super_admin", "hr_officer"], name: "Vacancies", desc: "Faculty and staff positions on the Careers page.", view: "jobs" },
  { roles: ["super_admin", "hr_officer"], name: "Job applications", desc: "CVs, shortlisting, interviews and offers.", view: "job-applications" },
  { roles: ["super_admin", "alumni_coordinator"], name: "Alumni verification", desc: "Check alumni registrations against college records; choose who's featured on the home page.", view: "alumni-review" },
  { roles: ["super_admin"], name: "Email log", desc: "Every email the website sent, and any that failed.", view: "email-log" },
];

function renderOverview() {
  const roles = myRoles();
  $("[data-greeting]").textContent = `Welcome, ${state.me.name.split(" ")[0]}`;
  const labels = state.me.roles.map((r) => r.role_name + (r.scope_label ? ` (${r.scope_label})` : ""));
  $("[data-role-summary]").textContent = labels.length ? `Signed in as ${labels.join(", ")}.` : "You don't have a dashboard role yet.";
  const mine = MODULES.filter((m) => m.roles.some((r) => roles.includes(r)));
  $("[data-modules]").innerHTML = mine.length
    ? mine.map((m) => `
      <li class="flex items-center gap-4 px-5 py-4">
        <div class="min-w-0 flex-1"><p class="font-semibold">${esc(m.name)}</p>${m.desc ? `<p class="text-[0.9375rem] text-ink-2">${esc(m.desc)}</p>` : ""}</div>
        ${m.view ? `<a class="link-arrow" href="#${m.view}">Open ${icon("arrow-right")}</a>` : `<span class="tag">Arrives in Phase ${m.phase}</span>`}
      </li>`).join("")
    : `<li class="flex items-center gap-4 px-5 py-4"><div class="min-w-0 flex-1"><p class="font-semibold">My activity</p><p class="text-[0.9375rem] text-ink-2">Events you registered for and clubs you belong to.</p></div><a class="link-arrow" href="#mine">Open ${icon("arrow-right")}</a></li>`;
}

/* ---------- users & access ---------- */

async function loadSummary() {
  try {
    const s = await api("/auth/users/summary");
    $("[data-summary-invited]").textContent = `${s.invited} invite${s.invited === 1 ? "" : "s"} not yet accepted`;
    $("[data-summary-invited-sub]").textContent = s.invited ? `Oldest sent ${s.oldest_invite_days} day${s.oldest_invite_days === 1 ? "" : "s"} ago` : "Everyone invited has signed in";
    $("[data-summary-expiring]").textContent = `${s.expiring.length} role${s.expiring.length === 1 ? "" : "s"} expire this week`;
    $("[data-summary-expiring-sub]").textContent = s.expiring.length ? [...new Set(s.expiring.map((e) => e.role_name))].join(", ") : "No roles expiring in the next 7 days";
    $("[data-summary-suspended]").textContent = `${s.suspended} suspended`;
  } catch (err) { if (err.status !== 401) console.warn(err); }
}

const STATUS_TAG = { active: "tag-leaf", invited: "tag-amber", suspended: "tag-om" };
const STATUS_LABEL = { active: "Active", invited: "Invited", suspended: "Suspended" };

function roleChips(u) {
  if (!u.roles.length) return `<span class="text-[0.875rem] text-ink-3">No roles</span>`;
  return u.roles.map((r) => {
    const own = u.id === state.me.id && r.role === "super_admin";
    return `
    <span class="tag gap-1 ${own ? "" : "pr-1"}">${esc(r.role_name)}${r.scope_label ? `<span class="font-normal text-brand-700">&nbsp;· ${esc(r.scope_label)}</span>` : ""}${r.expires_at ? `<span class="font-normal text-ink-3">&nbsp;· until ${esc(new Date(r.expires_at).toLocaleDateString("en-GB", { day: "numeric", month: "short" }))}</span>` : ""}
      ${own ? "" : `<button type="button" class="ml-0.5 inline-flex h-6 w-6 items-center justify-center rounded-sm hover:bg-brand-100 hover:text-om-700" data-remove-grant="${esc(r.id)}" data-user="${esc(u.id)}" aria-label="Remove ${esc(r.role_name)} from ${esc(u.name)}">${icon("x")}</button>`}
    </span>`;
  }).join(" ");
}

function lastActive(u) {
  return u.last_login_at ? relative(u.last_login_at) : `<span class="text-ink-3">Never signed in</span>`;
}

function actions(u) {
  const self = u.id === state.me.id;
  const suspendBtn = u.status === "suspended"
    ? `<button type="button" class="btn btn-ghost btn-sm" data-reactivate="${esc(u.id)}">${icon("check")}<span>Reactivate</span></button>`
    : `<button type="button" class="btn btn-ghost btn-sm text-om-700 hover:bg-om-50 hover:text-om-700" data-suspend="${esc(u.id)}" ${self ? 'aria-disabled="true" title="You can\'t suspend your own account"' : ""} aria-label="Suspend ${esc(u.name)}">${icon("user-x")}<span class="hidden xl:inline">Suspend</span></button>`;
  return `<div class="flex justify-end gap-1">
    <button type="button" class="btn btn-ghost btn-sm" data-add-role="${esc(u.email)}" aria-label="Add a role for ${esc(u.name)}">${icon("plus")}<span class="hidden xl:inline">Add role</span></button>
    ${suspendBtn}
  </div>`;
}

const avatar = (u) => `<span class="flex h-9 w-9 flex-none items-center justify-center rounded-full bg-brand-100 text-[0.8125rem] font-semibold text-brand-800">${esc(initials(u.name))}</span>`;

let usersById = new Map();

async function loadUsers() {
  const params = new URLSearchParams({
    q: $("[data-user-search]").value.trim(),
    role: $("[data-role-filter]").value,
    status: $("[data-status-filter]").value,
    kind: $("[data-kind-filter]").value,
    page: state.users.page,
    per_page: state.users.perPage,
  });
  const err = $("[data-user-error]");
  try {
    const data = await api(`/auth/users?${params}`);
    err.classList.add("hidden");
    state.users.total = data.total;
    usersById = new Map(data.items.map((u) => [u.id, u]));
    $("[data-user-rows]").innerHTML = data.items.map((u) => `
      <tr>
        <td><div class="flex items-center gap-3">${avatar(u)}<div class="min-w-0"><p class="font-semibold">${esc(u.name)}</p><p class="truncate text-[0.875rem] text-ink-3">${esc(u.email)}</p></div></div></td>
        <td><div class="flex flex-wrap gap-1.5">${roleChips(u)}</div></td>
        <td><span class="tag ${STATUS_TAG[u.status] || ""}">${STATUS_LABEL[u.status] || esc(u.status)}</span></td>
        <td class="whitespace-nowrap text-ink-2">${lastActive(u)}</td>
        <td>${actions(u)}</td>
      </tr>`).join("");
    $("[data-user-cards]").innerHTML = data.items.map((u) => `
      <li class="p-4">
        <div class="flex items-start gap-3">${avatar(u)}
          <div class="min-w-0 flex-1">
            <p class="font-semibold">${esc(u.name)}</p>
            <p class="truncate text-[0.875rem] text-ink-3">${esc(u.email)}</p>
            <div class="mt-2 flex flex-wrap gap-1.5">${roleChips(u)}</div>
            <div class="mt-2 flex flex-wrap items-center gap-3 text-[0.875rem] text-ink-2"><span class="tag ${STATUS_TAG[u.status] || ""}">${STATUS_LABEL[u.status] || esc(u.status)}</span><span>${lastActive(u)}</span></div>
          </div>
        </div>
        <div class="mt-3 border-t border-line-2 pt-2">${actions(u)}</div>
      </li>`).join("");
    $("[data-user-empty]").classList.toggle("hidden", data.items.length > 0);
    const from = data.total ? (data.page - 1) * data.per_page + 1 : 0;
    $("[data-user-count]").textContent = data.total ? `Showing ${from}–${from + data.items.length - 1} of ${data.total} users` : "";
    $('[data-page="-1"]').disabled = data.page <= 1;
    $('[data-page="1"]').disabled = from + data.items.length - 1 >= data.total;
  } catch (e) {
    if (e.status === 401) return;
    err.textContent = e.message;
    err.classList.remove("hidden");
  }
}

async function removeGrant(userId, grantId) {
  const u = usersById.get(userId);
  const grant = u?.roles.find((r) => r.id === grantId);
  try {
    await api(`/auth/users/${userId}/grants/${grantId}`, { method: "DELETE" });
    await Promise.all([loadUsers(), loadSummary()]);
    toast(`${icon("check")}<span>Removed ${esc(grant?.role_name)} from ${esc(u?.name)}.</span>`, {
      undo: () => grantRole({ email: u.email, role: grant.role, scope: grant.scope.replace(/^dept:/, ""), expires_at: grant.expires_at?.slice(0, 10) }, { quiet: true }),
    });
  } catch (err) { toastError(err); }
}

async function setSuspended(userId, suspend) {
  const u = usersById.get(userId);
  try {
    await api(`/auth/users/${userId}/${suspend ? "suspend" : "reactivate"}`, { method: "POST" });
    await Promise.all([loadUsers(), loadSummary()]);
    if (suspend) toast(`${icon("check")}<span>${esc(u?.name)} is suspended and signed out everywhere.</span>`, { undo: () => setSuspended(userId, false) });
    else toast(`${icon("check")}<span>${esc(u?.name)} can sign in again.</span>`);
  } catch (err) { toastError(err); }
}

async function grantRole(body, { quiet = false } = {}) {
  const res = await api("/auth/users/grants", { method: "POST", json: body });
  await Promise.all([loadUsers(), loadSummary()]);
  if (!quiet) {
    const r = res.user.roles.find((x) => x.role === body.role);
    toast(`${icon("check")}<span>${esc(r?.role_name || roleName(body.role))}${r?.scope_label ? ` (${esc(r.scope_label)})` : ""} granted to ${esc(res.user.email)}.${res.invited ? " They get it when they first sign in." : ""}</span>`);
  } else {
    toast(`${icon("check")}<span>Role restored.</span>`);
  }
  return res;
}

function initUsers() {
  const reload = () => { state.users.page = 1; loadUsers(); };
  $("[data-user-search]").addEventListener("input", debounce(reload));
  $("[data-role-filter]").addEventListener("change", reload);
  $("[data-status-filter]").addEventListener("change", reload);
  $("[data-kind-filter]").addEventListener("change", reload);
  $$("[data-page]").forEach((b) => b.addEventListener("click", () => { state.users.page += Number(b.dataset.page); loadUsers(); }));
  $$("[data-filter-status]").forEach((b) => b.addEventListener("click", () => { $("[data-status-filter]").value = b.dataset.filterStatus; reload(); }));

  document.addEventListener("click", (e) => {
    const rm = e.target.closest("[data-remove-grant]");
    if (rm) return removeGrant(rm.dataset.user, rm.dataset.removeGrant);
    const sus = e.target.closest("[data-suspend]");
    if (sus && sus.getAttribute("aria-disabled") !== "true") return setSuspended(sus.dataset.suspend, true);
    const rea = e.target.closest("[data-reactivate]");
    if (rea) return setSuspended(rea.dataset.reactivate, false);
    const add = e.target.closest("[data-add-role]");
    if (add) return openGrantSheet(add.dataset.addRole);
    if (e.target.closest("[data-open-grant]")) return openGrantSheet("");
  });

  // CSV import
  $("[data-import]").addEventListener("change", async (e) => {
    const file = e.target.files[0];
    e.target.value = "";
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    try {
      const res = await api("/auth/users/import", { method: "POST", body: form });
      $("[data-import-title]").textContent = `Import results: ${res.granted} granted, ${res.failed} failed`;
      $("[data-import-list]").innerHTML = res.results.map((r) => `
        <li class="flex gap-3 px-5 py-2.5">${r.ok ? `<span class="text-leaf-700">${icon("check")}</span>` : `<span class="text-om-700">${icon("circle-alert")}</span>`}
          <span class="w-16 flex-none text-ink-3">Row ${r.line}</span><span class="min-w-0 flex-1">${esc(r.email || "")} ${r.ok ? `· ${esc(roleName(r.role))}` : `· <span class="text-om-700">${esc(r.error)}</span>`}</span></li>`).join("");
      $("[data-import-results]").hidden = false;
      loadUsers(); loadSummary();
    } catch (err) { toastError(err); }
  });
  $("[data-import-close]").addEventListener("click", () => ($("[data-import-results]").hidden = true));
}

/* ---------- grant sheet ---------- */

function openGrantSheet(email) {
  const form = $("[data-grant-form]");
  form.reset();
  syncGrantRole();
  showGrantError("");
  form.querySelector("#g-email").value = email || "";
  site.drawers.setOpen(document.getElementById("grant-sheet"), true);
}

function populateRoleSelects() {
  $("[data-grant-role]").innerHTML = state.roles.map((r) => `<option value="${esc(r.code)}">${esc(r.name)}</option>`).join("");
  $("[data-grant-role]").value = "teacher";
  $("[data-grant-scope]").innerHTML = state.departments.map((d) => `<option value="${esc(d.code)}">${esc(d.name)}</option>`).join("");
  $("[data-role-filter]").innerHTML = `<option value="">All roles</option>` + state.roles.map((r) => `<option value="${esc(r.code)}">${esc(r.name)}</option>`).join("");
}

function syncGrantRole() {
  const role = $("[data-grant-role]").value;
  const spec = state.roles.find((r) => r.code === role);
  $("[data-scope-field]").hidden = spec?.scoped !== "dept";
  $("[data-super-warning]").hidden = role !== "super_admin";
}

function showGrantError(msg) {
  const error = $("#g-email-error");
  const email = $("#g-email");
  error.textContent = msg;
  error.classList.toggle("hidden", !msg);
  email.setAttribute("aria-invalid", String(Boolean(msg)));
  email.classList.toggle("border-om-600", Boolean(msg));
}

function initGrantForm() {
  const form = $("[data-grant-form]");
  $("[data-grant-role]").addEventListener("change", syncGrantRole);
  $("#g-email").addEventListener("input", () => showGrantError(""));
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const email = $("#g-email").value.trim().toLowerCase();
    const domain = state.domain || "ncit.edu.np";
    if (!email) return showGrantError("Enter the person's email address.");
    if (!email.endsWith(`@${domain}`)) return showGrantError(`Use an @${domain} address. Other accounts can't sign in to the dashboard.`);
    const role = $("[data-grant-role]").value;
    const scoped = state.roles.find((r) => r.code === role)?.scoped === "dept";
    const submit = $("[data-grant-submit]");
    submit.disabled = true;
    submit.textContent = "Granting…";
    try {
      await grantRole({ email, role, scope: scoped ? $("[data-grant-scope]").value : null, expires_at: $("#g-expiry").value || null });
      site.drawers.setOpen(document.getElementById("grant-sheet"), false);
    } catch (err) {
      if (err.code === "wrong_domain" || err.code === "invalid_email") showGrantError(err.message);
      else toastError(err);
    } finally {
      submit.disabled = false;
      submit.textContent = "Grant role";
    }
  });
}

/* ---------- audit log ---------- */

function describe(e) {
  const d = e.data || {};
  const who = (x) => esc(x || "someone");
  const role = `<strong class="font-semibold">${esc(d.role_name || d.role || "a role")}</strong>${d.scope_label ? ` (${esc(d.scope_label)})` : ""}`;
  switch (e.type) {
    case "user.signed_in": return `Signed in${d.method === "dev" ? " (development login)" : d.method === "email_code" ? ` with an emailed code (${esc(d.purpose === "alumni" ? "alumni" : "applicant")})` : " with Google"}`;
    case "user.sign_in_refused": return `<span class="text-om-700">Sign-in refused</span> for ${who(d.email)}: ${esc({ wrong_domain: "not an NCIT account", account_suspended: "account suspended", email_not_verified: "email not verified", state_mismatch: "expired or forged request", invalid_google_token: "invalid Google response", google_exchange_failed: "Google did not confirm", wrong_code: "wrong sign-in code" }[d.reason] || d.reason)}`;
    case "role.granted": return `Granted ${role} to ${who(d.email)}${d.invited ? " (invited)" : ""}`;
    case "role.revoked": return `Removed ${role} from ${who(d.email)}`;
    case "user.suspended": return `Suspended ${who(d.email)}`;
    case "user.reactivated": return `Reactivated ${who(d.email)}`;
    case "session.signed_out": return "Signed out";
    case "session.refresh_reused": return `<span class="text-om-700">Session ended</span>: an old sign-in token was reused`;
    case "users.imported": return `Imported roles from CSV: ${esc(d.granted)} granted, ${esc(d.failed)} failed`;
    case "department.created": return `Created the <strong class="font-semibold">${esc(d.department)}</strong> department (draft)`;
    case "department.published": return `Published the <strong class="font-semibold">${esc(d.department)}</strong> page`;
    case "department.unpublished": return `Hid the <strong class="font-semibold">${esc(d.department)}</strong> page from the website`;
    case "department.updated": return `Edited <strong class="font-semibold">${esc(d.department)}</strong>: ${esc((d.fields || []).map((f) => f.replace(/_/g, " ")).join(", "))}`;
    case "courses.updated": return `Updated semester ${esc(d.semester)} courses of ${esc(d.programme)} (${esc(d.count)} courses)`;
    default: {
      const ap = e.type.match(/^(applications|job_applications)\.([a-z_]+)$/);
      if (ap) {
        const what = ap[1] === "applications" ? `application <strong class="font-semibold">${esc(d.name || "")}</strong>${d.programme ? ` (${esc(d.programme)})` : ""}`
          : `application for <strong class="font-semibold">${esc(d.name || "a vacancy")}</strong>`;
        const verb = { submitted: d.resubmitted ? "Sent again" : "Sent", withdrawn: "Withdrew", under_review: "Started reviewing", documents_requested: "Asked for more documents for",
          accepted: "Accepted", waitlisted: "Waiting-listed", rejected: "Declined", shortlisted: "Shortlisted", interview: "Invited to interview:", offered: "Made an offer:" }[ap[2]] || ap[2];
        return `${verb} ${what}${d.applicant ? ` from ${who(d.applicant)}` : ""}${d.emailed ? " · emailed" : ""}`;
      }
      const al = e.type.match(/^alumni\.(submitted|verified|rejected)$/);
      if (al) return `${{ submitted: "Registered as alumni:", verified: "Verified alumni", rejected: "Couldn't verify alumni" }[al[1]]} <strong class="font-semibold">${esc(d.name || "")}</strong>${d.email ? ` (${who(d.email)})` : ""}`;
      const r = e.type.match(/^registrations\.(registered|waitlisted|cancelled|updated)$/);
      if (r) {
        const ev = `<strong class="font-semibold">${esc(d.name || "an event")}</strong>`;
        const moved = d.moved_up?.length ? `; ${esc(d.moved_up.join(", "))} moved up from the waiting list` : "";
        if (r[1] === "updated") return `Updated the registration of ${who(d.email)} for ${ev}${d.fields ? `: ${esc(d.fields.join(", "))}` : ""}${moved}`;
        return `${{ registered: "Registered for", waitlisted: "Joined the waiting list for", cancelled: "Cancelled their registration for" }[r[1]]} ${ev}${moved}`;
      }
      const mb = e.type.match(/^memberships\.(requested|withdrawn|left|approved|rejected|removed|updated)$/);
      if (mb) {
        const club = `<strong class="font-semibold">${esc(d.name || "a club")}</strong>`;
        return { requested: `Asked to join ${club}`, withdrawn: `Withdrew their request to join ${club}`, left: `Left ${club}`,
          approved: `Approved ${who(d.email)} as a member of ${club}`, rejected: `Declined ${who(d.email)}'s request to join ${club}`,
          removed: `Removed ${who(d.email)} from ${club}`, updated: `Set ${who(d.email)}'s position in ${club} to “${esc(d.position || "member")}”` }[mb[1]];
      }
      const c = e.type.match(/^(banners|leadership|news|notices|facilities|events|clubs|activities|intakes|offerings|jobs)\.(created|updated|deleted|published|unpublished)$/);
      if (c) {
        const verb = { created: "Added", updated: "Edited", deleted: "Deleted", published: "Published", unpublished: "Unpublished" }[c[2]];
        return `${verb} ${esc(d.label || c[1])} <strong class="font-semibold">${esc(d.name || "")}</strong>${d.fields ? `: ${esc(d.fields.map((f) => f.replace(/_/g, " ")).join(", "))}` : ""}`;
      }
      const m = e.type.match(/^(programmes|faculty|labs|testimonials)\.(created|updated|deleted)$/);
      if (m) {
        const what = { programmes: "programme", faculty: "faculty member", labs: "lab", testimonials: "testimonial" }[m[1]];
        return `${{ created: "Added", updated: "Edited", deleted: "Removed" }[m[2]]} ${what}${d.name ? ` <strong class="font-semibold">${esc(d.name)}</strong>` : ""} in ${esc(d.department)}`;
      }
      return esc(e.type);
    }
  }
}

async function loadAudit() {
  const params = new URLSearchParams({
    q: $("[data-audit-search]").value.trim(),
    type: $("[data-audit-type]").value,
    page: state.audit.page,
    per_page: state.audit.perPage,
  });
  try {
    const data = await api(`/audit/?${params}`);
    $("[data-audit-rows]").innerHTML = data.items.map((e) => `
      <tr>
        <td class="whitespace-nowrap text-ink-2"><time datetime="${esc(e.at)}" title="${esc(dateTime(e.at))}">${esc(relative(e.at))}</time></td>
        <td class="max-w-[16rem] truncate">${esc(e.actor.email || e.data?.email || "—")}</td>
        <td>${describe(e)}</td>
        <td class="hidden text-ink-3 md:table-cell">${esc(e.ip || "")}</td>
      </tr>`).join("");
    $("[data-audit-empty]").classList.toggle("hidden", data.items.length > 0);
    const from = data.total ? (data.page - 1) * data.per_page + 1 : 0;
    $("[data-audit-count]").textContent = data.total ? `Showing ${from}–${from + data.items.length - 1} of ${data.total}` : "";
    $('[data-audit-page="-1"]').disabled = data.page <= 1;
    $('[data-audit-page="1"]').disabled = from + data.items.length - 1 >= data.total;
  } catch (err) { if (err.status !== 401) toastError(err); }
}

function initAudit() {
  const reload = () => { state.audit.page = 1; loadAudit(); };
  $("[data-audit-search]").addEventListener("input", debounce(reload));
  $("[data-audit-type]").addEventListener("change", reload);
  $$("[data-audit-page]").forEach((b) => b.addEventListener("click", () => { state.audit.page += Number(b.dataset.auditPage); loadAudit(); }));
}

/* ---------- sign out, demo role preview ---------- */

function initSignOut() {
  $("[data-sign-out]").addEventListener("click", async () => {
    try { await rawFetch("/auth/logout", { method: "POST" }); } catch { /* signing out anyway */ }
    location.assign("/login.html?signed_out=1");
  });
}

function initDemoPreview() {
  const select = document.getElementById("role-preview");
  select.addEventListener("change", () => {
    const role = select.value;
    state.me.roles = [{ id: "demo", role, role_name: roleName(role), scope: role === "hod" ? "dept:computer" : "*", scope_label: role === "hod" ? "Computer Engineering" : "" }];
    filterMenu([role]);
    showView();
  });
}

/* ---------- start ---------- */

async function start() {
  state.demo = !(await backendAvailable());
  try {
    const [{ user }, catalogue, config] = await Promise.all([
      api("/auth/me"),
      api("/auth/roles"),
      state.demo ? Promise.resolve({ domain: "ncit.edu.np" }) : fetch(`${API}/auth/config`).then((r) => r.json()),
    ]);
    state.me = user;
    state.roles = catalogue.roles;
    state.departments = catalogue.departments;
    state.domain = config.domain;
  } catch (err) {
    if (err.status !== 401) {
      $("[data-loading]").textContent = "The dashboard couldn't load. Reload the page, or try again in a minute.";
    }
    return;
  }
  renderShell();
  populateRoleSelects();
  initUsers();
  initGrantForm();
  initAudit();
  initSignOut();
  initDepartments({ api, toast, toastError, esc, icon, drawers: site.drawers, isSuperAdmin });
  initContent({ api, toast, toastError, esc, icon, drawers: site.drawers, onAction: campusAction });
  initCampus({ api, toast, toastError, esc, icon, drawers: site.drawers, reload: reloadContent });
  initReview({ api, toast, toastError, esc, icon, drawers: site.drawers });
  if (myRoles().some((r) => r === "super_admin" || r === "eca_admin")) refreshBadge();
  if (state.demo) initDemoPreview();
  window.addEventListener("hashchange", showView);
  showView();
}

start();
