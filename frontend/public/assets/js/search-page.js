// Site search: results from search-service, filterable by kind, with matched words highlighted.

import { esc, icon } from "./content-shared.js";

const $ = (s) => document.querySelector(s);
const body = $('[data-c="body"]');
const params = new URLSearchParams(location.search);
const ICON = { page: "file-text", department: "layers", programme: "graduation-cap", faculty: "user", news: "megaphone",
  notice: "bell", event: "calendar-days", club: "trophy", job: "briefcase" };
const MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const day = (iso) => { const d = new Date(new Date(iso).getTime() + 345 * 60000); return `${d.getUTCDate()} ${MON[d.getUTCMonth()]} ${d.getUTCFullYear()}`; };
// the service marks matched words with invisible characters; show them as <mark> (after escaping everything else)
const highlight = (text) => esc(text).replace(/⁨/g, '<mark class="rounded-sm bg-amber-50 px-0.5 font-semibold text-ink">').replace(/⁩/g, "</mark>");

async function run() {
  const q = (params.get("q") || "").trim();
  const kind = params.get("kind") || "";
  const page = Math.max(Number(params.get("page") || 1), 1);
  $("#q").value = q;
  if (!q) {
    body.innerHTML = `<p class="text-ink-2">Type what you're looking for: a programme, a teacher's name, an exam notice, a club…</p>`;
    $("#q").focus();
    return;
  }
  document.title = `${q} · Search · NCIT`;
  body.innerHTML = `<p class="text-ink-2">Searching…</p>`;
  let data = null;
  try {
    const res = await fetch(`/api/v1/search/public/search?${new URLSearchParams(Object.entries({ q, kind, page }).filter(([, v]) => v))}`, { headers: { Accept: "application/json" } });
    if (res.ok && (res.headers.get("content-type") || "").includes("json")) data = await res.json();
  } catch { /* below */ }
  if (!data) {
    $('[data-c="preview-banner"]').classList.remove("hidden");
    body.innerHTML = `<p class="text-ink-2">Search isn't available right now. Try the menus above, or the <a class="font-semibold text-brand-700 hover:underline" href="/admissions">Admissions</a> and <a class="font-semibold text-brand-700 hover:underline" href="/notices">Notices</a> pages.</p>`;
    return;
  }
  const total = Object.values(data.kinds).reduce((a, b) => a + b, 0);
  const link = (k, p = 1) => `/search?${new URLSearchParams(Object.entries({ q, kind: k, page: p > 1 ? p : "" }).filter(([, v]) => v))}`;
  const chip = (k, label, n) => `<a href="${link(k)}" class="inline-flex min-h-10 items-center gap-2 rounded-sm border px-3.5 font-semibold ${kind === k ? "border-brand-700 bg-brand-50 text-brand-800" : "border-line text-ink-2 hover:border-brand-700"}" ${kind === k ? 'aria-current="page"' : ""}>${esc(label)} <span class="text-[0.875rem] font-normal text-ink-3">${n}</span></a>`;
  const pages = Math.ceil(data.total / data.per_page);
  body.innerHTML = !total ? `<p class="text-[1.125rem] text-ink-2">Nothing found for <strong class="text-ink">“${esc(q)}”</strong>. Check the spelling, or try fewer or different words.</p>`
    : `<nav class="flex flex-wrap gap-2" aria-label="Filter results">${chip("", "All", total)}${Object.entries(data.kinds).map(([k, n]) => chip(k, data.labels[k] || k, n)).join("")}</nav>
      <p class="mt-6 text-[0.9375rem] text-ink-3">${data.total} result${data.total === 1 ? "" : "s"} for “${esc(q)}”</p>
      <ol class="mt-2 divided border-y border-line">${data.items.map((r) => `
        <li class="group relative flex gap-4 py-5">
          <span class="mt-1 flex h-9 w-9 flex-none items-center justify-center rounded-sm bg-brand-50 text-brand-700">${icon(ICON[r.kind] || "file-text")}</span>
          <div class="min-w-0">
            <p class="text-[0.8125rem] font-semibold tracking-[0.04em] text-ink-3 uppercase">${esc(data.labels[r.kind] || r.kind)}${r.updated_at && ["news", "notice", "event"].includes(r.kind) ? ` · ${esc(day(r.updated_at))}` : ""}</p>
            <h2 class="mt-0.5 text-[1.1875rem] leading-snug font-semibold"><a class="after:absolute after:inset-0 group-hover:text-brand-700" href="${esc(r.url)}">${esc(r.title)}</a></h2>
            ${r.snippet ? `<p class="mt-1 max-w-[70ch] text-ink-2">${highlight(r.snippet)}</p>` : ""}
          </div>
        </li>`).join("")}</ol>
      ${pages > 1 ? `<nav class="mt-8 flex items-center justify-between" aria-label="Pages"><span class="text-ink-2">Page ${data.page} of ${pages}</span><span class="flex gap-2">${data.page > 1 ? `<a class="btn btn-outline btn-sm" href="${link(kind, data.page - 1)}">Previous</a>` : ""}${data.page < pages ? `<a class="btn btn-outline btn-sm" href="${link(kind, data.page + 1)}">Next</a>` : ""}</span></nav>` : ""}`;
}

run();
