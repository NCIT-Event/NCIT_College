// Login page: Google sign-in link, error messages, optional development login.

const params = new URLSearchParams(location.search);
// Where to go after signing in: only a path on this site. Browsers treat "\" as "/" and drop tabs and
// line breaks, so "/\evil.com" or "/<tab>/evil.com" would leave the site; reject those, then confirm the
// parsed URL is still on this origin.
export const safeNext = (n, origin = location.origin) => {
  const fallback = "/dashboard/";
  if (typeof n !== "string" || !/^\/(?![/\\])/.test(n) || /[\x00-\x20\x7f\\]/.test(n)) return fallback;
  try {
    const u = new URL(n, origin);
    return u.origin === origin ? u.pathname + u.search + u.hash : fallback;
  } catch {
    return fallback;
  }
};
const next = safeNext(params.get("next") || "/dashboard/");

const MESSAGES = {
  wrong_domain: "That Google account isn't an NCIT account. Sign in with your @ncit.edu.np address. If you're signed in to several Google accounts, choose the college one.",
  account_suspended: "This account is suspended. Contact the college IT office if you think this is a mistake.",
  email_not_verified: "Google hasn't verified this email address yet. Verify it with Google, then try again.",
  state_mismatch: "The sign-in took too long or was opened in another tab. Try again.",
  invalid_google_token: "Google's response couldn't be checked. Try again.",
  google_exchange_failed: "Google didn't confirm the sign-in. Try again in a moment.",
  google_not_configured: "Google sign-in isn't set up on this server yet. Ask the site administrator to add the Google OAuth client.",
  cancelled: "Sign-in was cancelled.",
  signed_out: "You've signed out.",
  backend_down: "The sign-in service isn't running. You can still look around the dashboard in demo mode.",
};

function show(code, tone = "error") {
  const box = document.querySelector("[data-message]");
  const text = MESSAGES[code] || "Sign-in didn't work. Try again.";
  box.querySelector("[data-message-text]").innerHTML = code === "backend_down"
    ? `${text} <a class="font-semibold underline underline-offset-2" href="/dashboard/">Open the demo</a>`
    : text;
  box.classList.remove("hidden");
  box.classList.add("flex");
  box.className = box.className.replace(/\b(bg|text)-(om|amber|leaf)-\d+\b/g, "");
  box.classList.add(...(tone === "info" ? ["bg-leaf-50", "text-leaf-700"] : tone === "warn" ? ["bg-amber-50", "text-amber-700"] : ["bg-om-50", "text-om-700"]));
}

const google = document.querySelector("[data-google]");
google.href = `/api/v1/auth/google/login?next=${encodeURIComponent(next)}`;

if (params.get("error")) show(params.get("error"));
else if (params.get("signed_out")) show("signed_out", "info");

async function init() {
  let config;
  try {
    const res = await fetch("/api/v1/auth/config", { headers: { Accept: "application/json" } });
    if (!res.ok || !(res.headers.get("content-type") || "").includes("json")) throw new Error("no backend");
    config = await res.json();
  } catch {
    show("backend_down", "warn");
    return;
  }
  document.querySelector("[data-domain]").textContent = `@${config.domain}`;

  // already signed in? go straight on
  const me = await fetch("/api/v1/auth/me", { credentials: "same-origin" });
  if (me.ok) { location.replace(next); return; }

  if (!config.google) {
    google.setAttribute("aria-disabled", "true");
    google.classList.add("pointer-events-none", "opacity-50");
    if (!params.get("error")) show("google_not_configured", "warn");
  }
  if (config.dev_login) {
    const form = document.querySelector("[data-dev-form]");
    form.hidden = false;
    const depts = ["computer", "it", "software", "ice", "civil", "architecture", "bca", "management"];
    document.querySelector("[data-demo-hods]").innerHTML = depts.map((d) =>
      `<button type="button" class="tag hover:bg-brand-100" data-fill="hod.${d}@${config.domain}">hod.${d}</button>`).join("");
    document.querySelector("[data-demo-admins]").innerHTML = ["content.admin", "event.admin", "eca.admin", "admissions.officer", "hr.officer", "alumni.coordinator", "student.demo"].map((a) =>
      `<button type="button" class="tag hover:bg-brand-100" data-fill="${a}@${config.domain}">${a}</button>`).join("");
    form.addEventListener("click", (e) => {
      const b = e.target.closest("[data-fill]");
      if (b) { document.getElementById("dev-email").value = b.dataset.fill; document.getElementById("dev-email").focus(); }
    });
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const email = document.getElementById("dev-email").value.trim();
      const res = await fetch("/api/v1/auth/dev/login", {
        method: "POST", credentials: "same-origin",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email }),
      });
      if (res.ok) location.assign(next);
      else show((await res.json().catch(() => ({}))).error?.code || "error");
    });
  }
}

init();
