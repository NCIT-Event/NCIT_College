// Home page: featured alumni from alumni-service (verified, listed and chosen by
// the Alumni Coordinator). The built-in sample cards stay when the service is down.

import { esc } from "./portal.js";
import { initPhotos } from "./site.js";

async function featuredAlumni() {
  const list = document.querySelector("[data-home-alumni]");
  if (!list) return;
  let items;
  try {
    const res = await fetch("/api/v1/alumni/public/featured", { headers: { Accept: "application/json" } });
    if (!res.ok || !(res.headers.get("content-type") || "").includes("json")) return;
    items = (await res.json()).items;
  } catch { return; }
  if (!items.length) return;
  list.innerHTML = items.map((a) => `<li>
      <div class="photo aspect-[4/5] rounded-sm">${a.photo ? `<img src="${esc(a.photo)}" alt="${esc(a.full_name)}" loading="lazy">` : ""}</div>
      <p class="mt-4 font-semibold">${esc(a.full_name)}</p>
      <p class="text-[0.9375rem] text-ink-2">${esc(a.programme)}, ${esc(a.graduation_year)}${a.current_role ? ` · ${esc(a.current_role)}` : ""}${a.city ? `, ${esc(a.city)}` : ""}</p>
    </li>`).join("");
  initPhotos(list);
}

featuredAlumni();
