// Shared by the applicant and alumni portals (Apply, Careers, Alumni):
// sign-in with an emailed one-time code, signed-in API calls and uploads.
// People with an @ncit.edu.np account can use Google sign-in instead.

import { esc, icon } from "./content-shared.js";

export { esc, icon };

const csrf = () => document.cookie.split("; ").find((c) => c.startsWith("ncit_csrf="))?.split("=")[1] || "";
let refreshing = null;

/** Call /api/v1/<path>. Options: method, json, form (FormData). Returns { ok, status, body }. */
export async function call(path, { method = "GET", json, form } = {}, retried = false) {
  const headers = { Accept: "application/json" };
  if (method !== "GET") headers["X-CSRF-Token"] = csrf();
  if (json !== undefined) headers["Content-Type"] = "application/json";
  let res;
  try {
    res = await fetch(`/api/v1/${path}`, { method, headers, credentials: "same-origin", body: form || (json === undefined ? undefined : JSON.stringify(json)) });
  } catch { return { ok: false, status: 0, body: null }; }
  const body = (res.headers.get("content-type") || "").includes("json") ? await res.json().catch(() => null) : null;
  if (res.status === 401 && !retried && csrf()) {
    refreshing ??= fetch("/api/v1/auth/refresh", { method: "POST", credentials: "same-origin", headers: { "X-CSRF-Token": csrf() } })
      .then((r) => r.ok).catch(() => false).finally(() => { refreshing = null; });
    if (await refreshing) return call(path, { method, json, form }, true);
  }
  return { ok: res.ok, status: res.status, body };
}

export const errorText = (res, fallback = "That didn't work. Try again.") =>
  res.status === 0 ? "You seem to be offline. Check your connection and try again." : res.body?.error?.message || fallback;

/** The signed-in user, or null. `offline` is true when the sign-in service doesn't answer at all. */
export async function currentUser() {
  const res = await call("auth/me");
  if (res.ok) return { user: res.body.user, offline: false };
  const offline = res.status === 0 || res.status === 404 || res.status >= 500 || !res.body;
  return { user: null, offline };
}

export async function signOut() {
  await call("auth/logout", { method: "POST" });
  location.reload();
}

/** Sign-in card: email → 6-digit code. Calls onDone(user) once signed in. */
export function signInCard(box, { purpose, title, lead, onDone }) {
  const next = encodeURIComponent(location.pathname + location.search);
  box.innerHTML = `<div class="rounded-sm border border-line bg-white p-6 sm:p-8">
    <h2 class="font-serif text-h3 font-semibold">${esc(title)}</h2>
    <p class="mt-2 max-w-[56ch] text-ink-2">${esc(lead)}</p>
    <form class="mt-6" data-otp-email novalidate>
      <label class="field-label" for="otp-email">Your email address</label>
      <div class="flex flex-col gap-2 sm:flex-row">
        <input id="otp-email" type="email" class="field sm:max-w-[24rem]" autocomplete="email" inputmode="email" required placeholder="you@gmail.com">
        <button class="btn btn-primary" type="submit">Email me a code</button>
      </div>
      <p class="mt-2 text-[0.875rem] text-ink-3">We'll send a 6-digit code. No password needed.</p>
    </form>
    <form class="mt-6 hidden" data-otp-code novalidate>
      <p class="text-ink-2" data-otp-sent></p>
      <label class="field-label mt-4" for="otp-code">Code</label>
      <div class="flex flex-col gap-2 sm:flex-row">
        <input id="otp-code" class="field font-semibold tracking-[0.3em] sm:max-w-[12rem]" inputmode="numeric" autocomplete="one-time-code" maxlength="6" pattern="\\d{6}" required>
        <button class="btn btn-primary" type="submit">Sign in</button>
      </div>
      <p class="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-[0.9375rem]"><button type="button" class="font-semibold text-brand-700 hover:underline" data-otp-again>Send a new code</button><button type="button" class="font-semibold text-brand-700 hover:underline" data-otp-change>Use a different email</button></p>
      <p class="mt-3 hidden rounded-sm bg-amber-50 px-3 py-2 text-[0.875rem] text-amber-700" data-otp-dev></p>
    </form>
    <p class="mt-3 text-[0.9375rem] font-semibold text-om-700" role="alert" data-otp-error></p>
    <p class="mt-6 border-t border-line pt-4 text-[0.9375rem] text-ink-2">NCIT student or staff? <a class="font-semibold text-brand-700 hover:underline" href="/login.html?next=${next}">Sign in with your college Google account</a></p>
  </div>`;
  const $ = (s) => box.querySelector(s);
  const emailForm = $("[data-otp-email]"), codeForm = $("[data-otp-code]"), err = $("[data-otp-error]");
  let email = "";
  const busy = (form, on) => form.querySelectorAll("button, input").forEach((el) => { el.disabled = on; });

  async function send() {
    err.textContent = "";
    busy(emailForm, true);
    const res = await call("auth/code/request", { method: "POST", json: { email, purpose } });
    busy(emailForm, false);
    if (!res.ok) { err.textContent = errorText(res); return false; }
    $("[data-otp-sent]").innerHTML = `We sent a code to <strong class="font-semibold text-ink">${esc(res.body.sent_to)}</strong>. It works for 10 minutes. Check your spam folder if it doesn't arrive.`;
    const dev = $("[data-otp-dev]");
    dev.classList.toggle("hidden", !res.body.dev_code);
    if (res.body.dev_code) dev.innerHTML = `<strong>Development only:</strong> no mail server is needed here. Your code is <strong>${esc(res.body.dev_code)}</strong>.`;
    emailForm.classList.add("hidden");
    codeForm.classList.remove("hidden");
    $("#otp-code").value = "";
    $("#otp-code").focus();
    return true;
  }
  emailForm.addEventListener("submit", (e) => {
    e.preventDefault();
    email = $("#otp-email").value.trim();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { err.textContent = "Enter a valid email address."; return; }
    send();
  });
  $("[data-otp-again]").addEventListener("click", send);
  $("[data-otp-change]").addEventListener("click", () => {
    codeForm.classList.add("hidden"); emailForm.classList.remove("hidden"); err.textContent = ""; $("#otp-email").focus();
  });
  codeForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    err.textContent = "";
    busy(codeForm, true);
    const res = await call("auth/code/verify", { method: "POST", json: { email, code: $("#otp-code").value } });
    busy(codeForm, false);
    if (res.ok) { onDone(res.body.user); return; }
    err.textContent = errorText(res);
    if (res.body?.error?.code === "code_expired") $("#otp-code").value = "";
  });
}

/** "Signed in as … · Sign out" line. */
export function signedInBar(user) {
  return `<p class="flex flex-wrap items-center gap-x-3 gap-y-1 text-[0.9375rem] text-ink-2">${icon("user")}Signed in as <strong class="font-semibold text-ink">${esc(user.email)}</strong>
    <button type="button" class="font-semibold text-brand-700 hover:underline" data-sign-out>Sign out</button></p>`;
}

document.addEventListener("click", (e) => { if (e.target.closest("[data-sign-out]")) signOut(); });

const MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
/** Nepal-time date (and time) for display, whatever the visitor's computer is set to. */
export function nptDate(iso, withTime = false) {
  if (!iso) return "";
  const d = new Date(new Date(iso).getTime() + 345 * 60000);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getUTCDate()} ${MON[d.getUTCMonth()]} ${d.getUTCFullYear()}${withTime ? `, ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}` : ""}`;
}

/** Public read with preview fallback (static preview without services). */
export async function loadPublic(service, path, previewKey) {
  try {
    const res = await fetch(`/api/v1/${service}/public/${path}`, { headers: { Accept: "application/json" } });
    if ((res.headers.get("content-type") || "").includes("json") && (res.ok || res.status === 404)) return { data: res.ok ? await res.json() : null };
  } catch { /* preview below */ }
  const p = await fetch("/assets/data/portal-preview.json").then((r) => r.json()).catch(() => null);
  return { data: p?.[previewKey] ?? null, preview: true };
}
