// Home page: upcoming events (event-service) and the club list (eca-service).
// The page ships with sample content built in; live data replaces it when the
// services answer, and the built-in content stays in a static preview.

import { esc, loadPublic, nepal, when } from "./campus-shared.js";

const pad2 = (n) => String(n).padStart(2, "0");

async function events() {
  const list = document.querySelector("[data-home-events]");
  if (!list) return;
  const { data, preview } = await loadPublic("events", "events?limit=4");
  if (!data || preview) return;
  list.innerHTML = data.items.length ? data.items.map((e) => `<li class="group relative flex gap-5 py-5">
      <div class="date-block"><span class="d">${pad2(nepal.day(e.start_at))}</span><span class="m">${nepal.month(e.start_at)}</span></div>
      <div class="min-w-0">
        <h3 class="text-[1.125rem] leading-snug font-semibold"><a href="/events/${esc(e.slug)}" class="after:absolute after:inset-0 group-hover:text-brand-700">${esc(e.title)}</a></h3>
        <p class="mt-1 text-[0.9375rem] text-ink-2">${esc(when(e))}${e.venue ? ` · ${esc(e.venue)}` : ""}</p>
      </div>
    </li>`).join("")
    : `<li class="py-5 text-ink-2">No upcoming events right now. <a class="font-semibold text-brand-700 hover:underline" href="/events?view=past">See past events</a></li>`;
}

async function clubs() {
  const list = document.querySelector("[data-home-clubs]");
  if (!list) return;
  const { data, preview } = await loadPublic("eca", "clubs");
  if (!data || preview || !data.items.length) return;
  list.innerHTML = data.items.map((c) => `<li><a class="inline-flex min-h-11 items-center rounded-sm border border-line px-4 font-semibold hover:border-brand-700 hover:text-brand-700" href="/clubs/${esc(c.slug)}">${esc(c.name)}</a></li>`).join("");
  document.querySelectorAll("[data-campus-static-note]").forEach((n) => n.remove());
}

events();
clubs();
