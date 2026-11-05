// Home page: banners, news, notices, leadership and facilities from content-service.
// The page ships with the same content built in, so it still reads well if the
// service is unreachable; live data replaces it when it arrives.

import { initCarousel, initPhotos } from "./site.js";
import { NOTICE_TAG, dateOnly, esc, icon, loadContent, noticeLink, shortDate } from "./content-shared.js";

const $ = (sel, root = document) => root.querySelector(sel);

function renderBanners(banners) {
  const root = $("[data-carousel]");
  if (!root || !banners.length) return;
  const stage = root.querySelector(".slide").parentElement;
  root.querySelectorAll(".slide").forEach((s) => s.remove());
  const controls = stage.querySelector("[data-goto]")?.closest(".absolute");
  const html = banners.map((b, i) => {
    const heading = i === 0 ? "h1" : "h2";
    const buttons = [
      b.cta_label && b.cta_url ? `<a href="${esc(b.cta_url)}" class="btn ${i === 0 ? "btn-light" : "btn-apply"}">${esc(b.cta_label)}</a>` : "",
      b.cta2_label && b.cta2_url ? `<a href="${esc(b.cta2_url)}" class="btn btn-outline-light">${esc(b.cta2_label)}</a>` : "",
    ].join("");
    return `<article class="slide absolute inset-0" aria-roledescription="slide" aria-label="${i + 1} of ${banners.length}" aria-hidden="${i !== 0}">
      <div class="photo photo-dark absolute inset-0">${b.image ? `<img src="${esc(b.image)}" alt="${esc(b.image_alt)}" ${i === 0 ? 'fetchpriority="high"' : 'loading="lazy"'}>` : ""}</div>
      <div class="absolute inset-0 bg-[linear-gradient(to_top,rgb(10_20_64/0.94)_0%,rgb(10_20_64/0.72)_40%,rgb(10_20_64/0.35)_68%,rgb(10_20_64/0.08)_90%)]"></div>
      <div class="wrap relative flex h-full flex-col justify-end pb-28 sm:pb-32">
        <div class="slide-copy max-w-[44rem]">
          <${heading} class="font-serif text-display font-semibold tracking-[-0.025em]">${esc(b.title)}</${heading}>
          ${b.subtitle ? `<p class="mt-5 max-w-[38rem] text-[1.125rem] leading-relaxed text-brand-100 sm:text-[1.25rem]">${esc(b.subtitle)}</p>` : ""}
          ${buttons ? `<div class="mt-8 flex flex-wrap gap-3">${buttons}</div>` : ""}
        </div>
      </div>
    </article>`;
  }).join("");
  controls.insertAdjacentHTML("beforebegin", html);
  const dots = root.querySelector('[aria-label="Choose slide"]');
  dots.innerHTML = banners.map((_, i) => `<button type="button" class="progress-dot h-11 w-12 bg-transparent" data-goto="${i}" aria-label="Show slide ${i + 1}"><span></span></button>`).join("");
  dots.parentElement.hidden = banners.length < 2;
  initPhotos(root);
  initCarousel(root);
}

function renderNews(news) {
  const box = $("[data-home-news]");
  if (!box || !news.length) return;
  const [lead, ...rest] = news;
  const meta = (a) => `<time datetime="${esc(dateOnly(a.publish_at))}">${esc(shortDate(a.publish_at))}</time>`;
  box.innerHTML = `
    <article class="group relative lg:col-span-7">
      <div class="photo aspect-[16/10] rounded-sm">${lead.cover ? `<img src="${esc(lead.cover)}" alt="${esc(lead.cover_alt)}" loading="lazy">` : ""}</div>
      <p class="mt-5 flex flex-wrap items-center gap-3 text-[0.9375rem] text-ink-3">${lead.category ? `<span class="tag">${esc(lead.category)}</span>` : ""}${meta(lead)}</p>
      <h3 class="mt-3 font-serif text-[1.75rem] leading-tight font-semibold tracking-[-0.01em] sm:text-[2rem]"><a href="/news/${esc(lead.slug)}" class="after:absolute after:inset-0 group-hover:text-brand-700">${esc(lead.title)}</a></h3>
      ${lead.summary ? `<p class="mt-3 max-w-[60ch] text-ink-2">${esc(lead.summary)}</p>` : ""}
    </article>
    <div class="divided border-t border-line lg:col-span-5 lg:border-t-0">${rest.map((a, i) => `
      <article class="group relative flex gap-5 py-6 ${i === 0 ? "lg:pt-0" : ""}">
        <div class="photo aspect-square w-24 flex-none rounded-sm sm:w-28">${a.cover ? `<img src="${esc(a.cover)}" alt="" loading="lazy">` : ""}</div>
        <div>
          <p class="flex flex-wrap items-center gap-2 text-[0.875rem] text-ink-3">${meta(a)}</p>
          <h3 class="mt-1.5 text-[1.125rem] leading-snug font-semibold"><a href="/news/${esc(a.slug)}" class="after:absolute after:inset-0 group-hover:text-brand-700">${esc(a.title)}</a></h3>
        </div>
      </article>`).join("")}</div>`;
  initPhotos(box);
}

function renderNotices(notices) {
  const list = $("[data-home-notices]");
  if (!list) return;
  list.innerHTML = notices.length ? notices.map((n) => {
    const [cls, label] = NOTICE_TAG[n.category] || NOTICE_TAG.general;
    const link = noticeLink(n);
    return `<li class="group relative flex items-start gap-4 py-5">
      <div class="min-w-0 flex-1">
        <p class="flex flex-wrap items-center gap-2 text-[0.875rem] text-ink-3"><span class="tag ${cls}">${label}</span><time datetime="${esc(dateOnly(n.publish_at))}">${esc(shortDate(n.publish_at))}</time>${n.pinned ? `<span class="text-[0.8125rem] font-semibold text-om-700">Pinned</span>` : ""}</p>
        <h3 class="mt-2 font-semibold leading-snug"><a href="${esc(link.href)}" ${link.external ? 'rel="noopener" target="_blank"' : ""} class="after:absolute after:inset-0 group-hover:text-brand-700">${esc(n.title)}</a></h3>
      </div>
      ${link.icon ? `<svg class="icon mt-1 text-ink-3" role="img" aria-label="${link.label}"><use href="/assets/img/icons.svg#i-${link.icon}"/></svg>` : ""}
    </li>`;
  }).join("") : `<li class="py-8 text-ink-2">No current notices.</li>`;
}

function renderLeadership(people) {
  const box = $("[data-home-leadership]");
  if (!box || !people.length) return;
  const [lead, ...rest] = people;
  box.innerHTML = `
    <figure class="grid gap-8 sm:grid-cols-[minmax(0,14rem)_1fr] lg:col-span-7">
      <div class="photo aspect-[4/5] max-w-[14rem] rounded-sm">${lead.photo ? `<img src="${esc(lead.photo)}" alt="${esc(lead.person_name)}, ${esc(lead.role_title)}" loading="lazy" class="object-top">` : ""}</div>
      <div>
        ${icon("quote", "h-9 w-9 text-brand-200")}
        <blockquote class="mt-3 font-serif text-[1.375rem] leading-snug text-ink sm:text-[1.625rem]"><p>${esc(lead.excerpt)}</p></blockquote>
        <figcaption class="mt-6">
          <span class="block font-semibold">${esc(lead.person_name)}</span>
          <span class="block text-ink-2">${esc(lead.role_title)}</span>
          <a class="link-arrow mt-3" href="/leadership#${esc(lead.position)}">Read the full message ${icon("arrow-right")}</a>
        </figcaption>
      </div>
    </figure>
    <div class="divided self-start border-y border-line lg:col-span-5">${rest.map((m) => `
      <figure class="flex gap-5 py-6">
        <div class="photo aspect-[4/5] w-20 flex-none rounded-sm">${m.photo ? `<img src="${esc(m.photo)}" alt="${esc(m.person_name)}, ${esc(m.role_title)}" loading="lazy" class="object-top">` : ""}</div>
        <div>
          ${m.excerpt ? `<blockquote class="text-ink-2"><p>“${esc(m.excerpt)}”</p></blockquote>` : ""}
          <figcaption class="mt-3"><span class="block font-semibold">${esc(m.person_name)}</span><span class="block text-[0.9375rem] text-ink-3">${esc(m.role_title)}</span><a class="link-arrow mt-2 text-[0.9375rem]" href="/leadership#${esc(m.position)}">Read message ${icon("arrow-right")}</a></figcaption>
        </div>
      </figure>`).join("")}</div>`;
  initPhotos(box);
}

function renderFacilities(items) {
  const list = $("[data-home-facilities]");
  if (!list || !items.length) return;
  list.innerHTML = items.map((f) => `<li class="flex items-center gap-3 border-b border-line py-3">${icon(f.icon || "building-2", "icon text-brand-700")}${esc(f.name)}</li>`).join("");
}

async function start() {
  const { data, preview } = await loadContent("home");
  if (!data || preview) return; // keep the built-in content when there's no live service
  renderBanners(data.banners);
  renderNews(data.news);
  renderNotices(data.notices);
  renderLeadership(data.leadership);
  renderFacilities(data.facilities);
  document.querySelectorAll("[data-home-static-note]").forEach((n) => n.remove());
}

start();
