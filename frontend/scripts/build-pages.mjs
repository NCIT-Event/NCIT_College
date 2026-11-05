// Assemble pages: src/pages/**/*.html with <!-- @include name --> -> public/.
// Shared header, footer and nav live once in src/partials/.
import { readFileSync, writeFileSync, mkdirSync, readdirSync, statSync } from "node:fs";
import { join, dirname, relative } from "node:path";

const SRC = "src/pages";
const PARTIALS = "src/partials";
const OUT = "public";

const include = (html, depth = 0) =>
  html.replace(/<!--\s*@include\s+([\w-]+)\s*-->/g, (_, name) => {
    if (depth > 5) throw new Error(`include depth exceeded at ${name}`);
    return include(readFileSync(join(PARTIALS, `${name}.html`), "utf8"), depth + 1);
  });

const walk = (dir) =>
  readdirSync(dir).flatMap((f) => {
    const p = join(dir, f);
    return statSync(p).isDirectory() ? walk(p) : p.endsWith(".html") ? [p] : [];
  });

// Sharing and search-engine tags, built from each page's own <title> and description.
// Template pages that serve many addresses (one department, article, event…) get
// no canonical link: the address in the browser is the real one.
const SITE = (process.env.SITE_URL || "https://ncit.edu.np").replace(/\/$/, "");
const TEMPLATES = new Set(["department.html", "news.html", "event.html", "club.html", "job.html"]);
const PRIVATE = new Set(["login.html", "dashboard/index.html", "apply.html", "alumni/join.html"]);
const attr = (s) => s.replace(/&(?!amp;|lt;|gt;|quot;|#)/g, "&amp;").replace(/"/g, "&quot;");

function seo(html, rel) {
  const title = (html.match(/<title>([^<]*)<\/title>/) || [])[1] || "NCIT";
  const desc = (html.match(/<meta name="description" content="([^"]*)"/) || [])[1] || "";
  const path = "/" + rel.replace(/index\.html$/, "").replace(/\.html$/, "");
  const tags = [
    `<meta property="og:site_name" content="Nepal College of Information Technology">`,
    `<meta property="og:type" content="website">`,
    `<meta property="og:title" content="${attr(title)}">`,
    desc && `<meta property="og:description" content="${attr(desc)}">`,
    `<meta property="og:image" content="${SITE}/assets/img/og-image.jpg">`,
    `<meta name="twitter:card" content="summary_large_image">`,
    !TEMPLATES.has(rel) && !PRIVATE.has(rel) && `<link rel="canonical" href="${SITE}${path === "/" ? "/" : path}">`,
    !TEMPLATES.has(rel) && !PRIVATE.has(rel) && `<meta property="og:url" content="${SITE}${path}">`,
    PRIVATE.has(rel) && `<meta name="robots" content="noindex">`,
  ].filter(Boolean).join("\n");
  return html.replace("</head>", `${tags}\n</head>`);
}

for (const file of walk(SRC)) {
  const rel = relative(SRC, file);
  const out = join(OUT, rel);
  mkdirSync(dirname(out), { recursive: true });
  writeFileSync(out, seo(include(readFileSync(file, "utf8")), rel));
  console.log("page", out);
}
