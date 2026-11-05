// News (list and article), Notices and Leadership pages, filled from content-service.

import { initPhotos } from "./site.js";
import { NOTICE_TAG, dateOnly, esc, icon, loadContent, longDate, noticeLink, paragraphs, shortDate } from "./content-shared.js";

const $ = (sel, root = document) => root.querySelector(sel);
const body = $('[data-c="body"]');
const page = document.body.dataset.page;

function showPreview(flag) {
  if (flag) $('[data-c="preview-banner"]').classList.remove("hidden");
}

function pager(data, base) {
  const pages = Math.ceil(data.total / data.per_page);
  if (pages <= 1) return "";
  const link = (p, label) => `<a class="btn btn-outline btn-sm" href="${base}${base.includes("?") ? "&" : "?"}page=${p}">${label}</a>`;
  return `<nav class="mt-10 flex items-center justify-between gap-4" aria-label="Pages">
    <span class="text-ink-2">Page ${data.page} of ${pages}</span>
    <span class="flex gap-2">${data.page > 1 ? link(data.page - 1, "Previous") : ""}${data.page < pages ? link(data.page + 1, "Next") : ""}</span>
  </nav>`;
}

/* ---------- news ---------- */

async function newsList() {
  const params = new URLSearchParams(location.search);
  const { data, preview } = await loadContent(`news?page=${Number(params.get("page") || 1)}`);
  showPreview(preview);
  if (!data) { body.innerHTML = `<p class="text-ink-2">News couldn't be loaded. Try again in a minute.</p>`; return; }
  if (!data.items.length) { body.innerHTML = `<p class="text-ink-2">No news yet.</p>`; return; }
  body.innerHTML = `<ul class="grid gap-x-8 gap-y-12 sm:grid-cols-2 lg:grid-cols-3">${data.items.map((a) => `
    <li class="group relative">
      <div class="photo aspect-[16/10] rounded-sm">${a.cover ? `<img src="${esc(a.cover)}" alt="${esc(a.cover_alt)}" loading="lazy">` : ""}</div>
      <p class="mt-4 flex flex-wrap items-center gap-3 text-[0.9375rem] text-ink-3">${a.category ? `<span class="tag">${esc(a.category)}</span>` : ""}<time datetime="${esc(dateOnly(a.publish_at))}">${esc(shortDate(a.publish_at))}</time></p>
      <h2 class="mt-2 font-serif text-[1.375rem] leading-snug font-semibold"><a href="/news/${esc(a.slug)}" class="after:absolute after:inset-0 group-hover:text-brand-700">${esc(a.title)}</a></h2>
      ${a.summary ? `<p class="mt-2 text-ink-2">${esc(a.summary)}</p>` : ""}
    </li>`).join("")}</ul>${pager(data, "/news")}`;
  initPhotos(body);
}

async function newsArticle(slug) {
  const { data, preview } = await loadContent(`news/${encodeURIComponent(slug)}`);
  showPreview(preview);
  if (!data) {
    $('[data-c="title"]').textContent = "Article not found";
    $('[data-c="lead"]').textContent = "It may have been removed or not published yet.";
    body.innerHTML = `<a class="btn btn-primary" href="/news">All news</a>`;
    return;
  }
  const a = data.article;
  document.title = `${a.title} · NCIT`;
  $('meta[name="description"]')?.setAttribute("content", a.summary || a.title);
  $('[data-c="crumbs"]').innerHTML = `<a class="hover:text-brand-700" href="/news">News</a>`;
  $('[data-c="title"]').textContent = a.title;
  $('[data-c="lead"]').innerHTML = `${a.category ? `<span class="tag mr-2 align-middle">${esc(a.category)}</span>` : ""}<time datetime="${esc(dateOnly(a.publish_at))}">${esc(longDate(a.publish_at))}</time>`;
  body.innerHTML = `<article class="mx-auto max-w-[46rem]">
    ${a.cover ? `<div class="photo mb-8 aspect-[16/9] rounded-sm"><img src="${esc(a.cover)}" alt="${esc(a.cover_alt)}"></div>` : ""}
    ${a.summary ? `<p class="font-serif text-[1.375rem] leading-snug text-ink">${esc(a.summary)}</p>` : ""}
    <div class="mt-6 space-y-5 text-[1.125rem] leading-relaxed text-ink-2">${paragraphs(a.body)}</div>
    <p class="mt-12 border-t border-line pt-6"><a class="link-arrow" href="/news">${icon("chevron-left")} All news</a></p>
  </article>`;
  initPhotos(body);
}

/* ---------- notices ---------- */

async function notices() {
  const params = new URLSearchParams(location.search);
  const category = params.get("category") || "";
  const { data, preview } = await loadContent(`notices?page=${Number(params.get("page") || 1)}${category ? `&category=${encodeURIComponent(category)}` : ""}`);
  showPreview(preview);
  const filters = [["", "All"], ...Object.entries(NOTICE_TAG).map(([k, [, label]]) => [k, label])].map(([k, label]) =>
    `<a href="/notices${k ? `?category=${k}` : ""}" class="inline-flex min-h-10 items-center rounded-sm border px-4 font-semibold ${k === category ? "border-brand-700 bg-brand-50 text-brand-800" : "border-line text-ink-2 hover:border-brand-700"}" ${k === category ? 'aria-current="page"' : ""}>${label}</a>`).join("");
  if (!data) { body.innerHTML = `<p class="text-ink-2">Notices couldn't be loaded. Try again in a minute.</p>`; return; }
  body.innerHTML = `<nav class="flex flex-wrap gap-2" aria-label="Notice categories">${filters}</nav>
    ${data.items.length ? `<ul class="mt-8 divided border-y border-line">${data.items.map((n) => {
      const [cls, label] = NOTICE_TAG[n.category] || NOTICE_TAG.general;
      const link = noticeLink(n);
      const action = link.label ? `<a class="btn btn-outline btn-sm flex-none" href="${esc(link.href)}" ${link.external ? 'rel="noopener" target="_blank"' : ""}>${icon(link.icon)}${link.label === "PDF" ? "Download PDF" : "Open link"}</a>` : "";
      return `<li id="notice-${esc(n.id)}" class="flex flex-col gap-3 py-6 sm:flex-row sm:items-start sm:justify-between sm:gap-8">
        <div class="min-w-0">
          <p class="flex flex-wrap items-center gap-2 text-[0.875rem] text-ink-3"><span class="tag ${cls}">${label}</span><time datetime="${esc(dateOnly(n.publish_at))}">${esc(longDate(n.publish_at))}</time>${n.pinned ? `<span class="text-[0.8125rem] font-semibold text-om-700">Pinned</span>` : ""}</p>
          <h2 class="mt-2 text-[1.1875rem] font-semibold leading-snug">${esc(n.title)}</h2>
          ${n.body ? `<div class="mt-2 max-w-[66ch] space-y-2 text-ink-2">${paragraphs(n.body)}</div>` : ""}
        </div>${action}
      </li>`;
    }).join("")}</ul>${pager(data, `/notices${category ? `?category=${category}` : ""}`)}`
    : `<p class="mt-8 text-ink-2">No current notices in this category.</p>`}`;
  if (location.hash) document.getElementById(location.hash.slice(1))?.scrollIntoView();
}

/* ---------- leadership ---------- */

async function leadership() {
  const { data, preview } = await loadContent("leadership");
  showPreview(preview);
  if (!data?.items.length) { body.innerHTML = `<p class="text-ink-2">Messages will appear here soon.</p>`; return; }
  body.innerHTML = data.items.map((m, i) => `
    <article id="${esc(m.position)}" class="${i ? "mt-16 border-t border-line pt-16" : ""} grid scroll-mt-32 gap-8 md:grid-cols-[14rem_1fr] md:gap-12" aria-labelledby="${esc(m.position)}-name">
      <div class="photo aspect-[4/5] w-40 rounded-sm md:w-56">${m.photo ? `<img src="${esc(m.photo)}" alt="${esc(m.person_name)}, ${esc(m.role_title)}" class="object-top" loading="lazy">` : ""}</div>
      <div class="max-w-[66ch]">
        <h2 id="${esc(m.position)}-name" class="font-serif text-h3 font-semibold">${esc(m.person_name)}</h2>
        <p class="text-ink-2">${esc(m.role_title)}</p>
        ${m.excerpt ? `<blockquote class="mt-6 font-serif text-[1.375rem] leading-snug text-ink">“${esc(m.excerpt)}”</blockquote>` : ""}
        <div class="mt-6 space-y-4 text-[1.0625rem] leading-relaxed text-ink-2">${paragraphs(m.message)}</div>
      </div>
    </article>`).join("");
  initPhotos(body);
  if (location.hash) document.getElementById(location.hash.slice(1))?.scrollIntoView();
}

const articleSlug = location.pathname.match(/^\/news\/([a-z0-9-]+)\/?$/)?.[1] || (page === "news" && new URLSearchParams(location.search).get("a"));
if (page === "news") (articleSlug ? newsArticle(articleSlug) : newsList());
if (page === "notices") notices();
if (page === "leadership") leadership();
