// Local static server for previews: serves public/ and mirrors the gateway's
// rewrites of /departments/<slug>, /news/<slug>, /events/<slug>, /clubs/<slug> and /careers/<slug> to their templates.
// With BACKEND=http://localhost:8080 it also forwards /api/ and /media/ there.
import { createServer } from "node:http";
import { readFile, stat } from "node:fs/promises";
import { extname, join, normalize } from "node:path";

const ROOT = new URL("../public/", import.meta.url).pathname;
const PORT = Number(process.env.PORT || 5173);
const BACKEND = process.env.BACKEND || "";
const TYPES = { ".html": "text/html; charset=utf-8", ".css": "text/css", ".js": "text/javascript", ".json": "application/json",
  ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp", ".woff2": "font/woff2", ".md": "text/plain" };

createServer(async (req, res) => {
  const url = new URL(req.url, "http://local");
  if (BACKEND && (url.pathname.startsWith("/api/") || url.pathname.startsWith("/media/"))) {
    const body = ["GET", "HEAD"].includes(req.method) ? undefined : req;
    const upstream = await fetch(BACKEND + req.url, { method: req.method, headers: req.headers, body, duplex: "half", redirect: "manual" }).catch(() => null);
    if (!upstream) { res.writeHead(502).end(); return; }
    res.writeHead(upstream.status, Object.fromEntries(upstream.headers));
    res.end(Buffer.from(await upstream.arrayBuffer()));
    return;
  }
  let path = url.pathname;
  if (/^\/departments\/[a-z0-9-]+\/?$/.test(path)) path = "/department.html";
  if (/^\/news\/[a-z0-9-]+\/?$/.test(path)) path = "/news.html";
  if (/^\/events\/[a-z0-9-]+\/?$/.test(path)) path = "/event.html";
  if (/^\/clubs\/[a-z0-9-]+\/?$/.test(path)) path = "/club.html";
  if (/^\/careers\/[a-z0-9-]+\/?$/.test(path)) path = "/job.html";
  if (/^\/[a-z0-9/-]+$/.test(path) && !path.endsWith("/")) path += ".html"; // /news, /events, /apply, /alumni/join …
  if (path.endsWith("/")) path += "index.html";
  const file = normalize(join(ROOT, decodeURIComponent(path)));
  if (!file.startsWith(ROOT)) { res.writeHead(403).end(); return; }
  try {
    if ((await stat(file)).isDirectory()) throw new Error("dir");
    res.writeHead(200, { "Content-Type": TYPES[extname(file)] || "application/octet-stream" });
    res.end(await readFile(file));
  } catch {
    res.writeHead(404, { "Content-Type": "text/plain" }).end("Not found");
  }
}).listen(PORT, () => console.log(`Preview at http://localhost:${PORT}${BACKEND ? ` (API -> ${BACKEND})` : ""}`));
