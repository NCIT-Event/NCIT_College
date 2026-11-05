// Home page: replace the built-in department list with the published list
// from academics-service, so new or renamed departments appear automatically.
// If the service can't be reached, the list already in the page stays.

const list = document.querySelector("[data-department-list]");
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

async function refresh() {
  if (!list) return;
  try {
    const res = await fetch("/api/v1/academics/public/departments", { headers: { Accept: "application/json" } });
    if (!res.ok || !(res.headers.get("content-type") || "").includes("json")) return;
    const { items } = await res.json();
    if (!items.length) return;
    list.innerHTML = items.map((d) => `
      <li class="border-b border-line"><a href="/departments/${esc(d.slug)}" class="group flex items-center gap-6 py-6">
        <span class="flex-1"><span class="block font-serif text-h3 font-semibold text-ink group-hover:text-brand-700">${esc(d.name)}</span>
        <span class="mt-1 block text-ink-2">${esc(d.programmes.join(" · "))}</span></span>
        <svg class="icon flex-none text-ink-3 transition-transform duration-300 group-hover:translate-x-1 group-hover:text-brand-700" aria-hidden="true"><use href="/assets/img/icons.svg#i-arrow-right"/></svg>
      </a></li>`).join("");
  } catch { /* keep the built-in list */ }
}

refresh();
