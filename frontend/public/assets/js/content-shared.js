// Helpers shared by the home page and the News, Notices and Leadership pages.
// Content comes from content-service (/api/v1/content/public/...). With no
// backend (static preview), bundled preview data is used and labelled.

export const ICONS = "/assets/img/icons.svg";
export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
export const icon = (id, cls = "icon-sm") => `<svg class="${cls}" aria-hidden="true"><use href="${ICONS}#i-${id}"/></svg>`;
export const paragraphs = (text, cls = "") => String(text || "").split(/\n\s*\n/).filter((p) => p.trim())
  .map((p) => `<p class="${cls}">${esc(p.trim()).replace(/\n/g, "<br>")}</p>`).join("");
export const longDate = (iso) => new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });
export const shortDate = (iso) => new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
export const dateOnly = (iso) => new Date(iso).toISOString().slice(0, 10);

export const NOTICE_TAG = { exam: ["tag-om", "Exam"], admission: ["", "Admission"], holiday: ["tag-leaf", "Holiday"], result: ["tag-amber", "Result"], general: ["", "General"] };

export function noticeLink(n) {
  if (n.attachment) return { href: n.attachment, icon: "file-text", label: "PDF", external: false };
  if (n.link_url) return { href: n.link_url, icon: n.link_url.startsWith("/") ? "arrow-right" : "external-link", label: "Link", external: !n.link_url.startsWith("/") };
  return { href: `/notices#notice-${n.id}`, icon: "", label: "", external: false };
}

let previewCache;
async function preview() {
  previewCache ??= fetch("/assets/data/content-preview.json").then((r) => r.json()).catch(() => null);
  return previewCache;
}

/** GET a public content endpoint; returns { data, preview } or { data: null } when unavailable. */
export async function loadContent(path) {
  try {
    const res = await fetch(`/api/v1/content/public/${path}`, { headers: { Accept: "application/json" } });
    const json = (res.headers.get("content-type") || "").includes("json");
    if (json && (res.ok || res.status === 404)) return { data: res.ok ? await res.json() : null, status: res.status };
  } catch { /* fall back to preview data */ }
  const p = await preview();
  if (!p) return { data: null, status: 0 };
  const [base, query] = path.split("?");
  const params = new URLSearchParams(query || "");
  if (base === "home") return { data: p.home, preview: true };
  if (base === "leadership") return { data: { items: p.home.leadership }, preview: true };
  if (base === "notices") {
    const cat = params.get("category");
    const items = p.notices.filter((n) => !cat || n.category === cat);
    return { data: { items, total: items.length, page: 1, per_page: 50 }, preview: true };
  }
  if (base === "news") return { data: { items: p.news, total: p.news.length, page: 1, per_page: 50 }, preview: true };
  if (base.startsWith("news/")) {
    const article = p.news.find((a) => a.slug === base.slice(5));
    return article ? { data: { article }, preview: true } : { data: null, status: 404, preview: true };
  }
  return { data: null, status: 0 };
}
