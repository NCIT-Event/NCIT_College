// Shared behaviour for public pages and the dashboard shell. No framework.

const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const finePointer = window.matchMedia("(hover: hover) and (pointer: fine)").matches;

/* Photo slots: show the labelled placeholder until a real photo exists. */
export function initPhotos(root = document) {
  root.querySelectorAll(".photo > img, .logo-mark > img").forEach((img) => {
    const slot = img.parentElement;
    const missing = () => slot.classList.add("is-missing");
    if (img.complete && img.naturalWidth === 0) missing();
    img.addEventListener("error", missing, { once: true });
  });
}

/* Mega menus: click to toggle, hover-intent on desktop, Esc/outside to close. */
function initMegaMenus() {
  const triggers = [...document.querySelectorAll("[data-mega]")];
  if (!triggers.length) return;
  let hoverTimer;

  const panelOf = (btn) => document.getElementById(btn.getAttribute("aria-controls"));
  const close = (btn) => {
    btn.setAttribute("aria-expanded", "false");
    panelOf(btn)?.classList.remove("is-open");
  };
  const closeAll = (except) => triggers.forEach((b) => b !== except && close(b));
  const open = (btn) => {
    closeAll(btn);
    btn.setAttribute("aria-expanded", "true");
    panelOf(btn)?.classList.add("is-open");
  };

  triggers.forEach((btn) => {
    const panel = panelOf(btn);
    btn.addEventListener("click", () =>
      btn.getAttribute("aria-expanded") === "true" ? close(btn) : open(btn)
    );
    if (finePointer) {
      const enter = () => { clearTimeout(hoverTimer); hoverTimer = setTimeout(() => open(btn), 120); };
      const leave = () => { clearTimeout(hoverTimer); hoverTimer = setTimeout(() => close(btn), 180); };
      btn.addEventListener("mouseenter", enter);
      btn.addEventListener("mouseleave", leave);
      panel?.addEventListener("mouseenter", () => clearTimeout(hoverTimer));
      panel?.addEventListener("mouseleave", leave);
    }
    panel?.addEventListener("focusout", (e) => {
      if (!panel.contains(e.relatedTarget) && e.relatedTarget !== btn) close(btn);
    });
  });

  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    const openBtn = triggers.find((b) => b.getAttribute("aria-expanded") === "true");
    if (openBtn) { close(openBtn); openBtn.focus(); }
  });
  document.addEventListener("click", (e) => {
    if (!e.target.closest("[data-mega], .mega")) closeAll();
  });
}

/* Drawers: mobile nav, dashboard sidebar, side sheets. */
function initDrawers() {
  let lastFocus = null;

  const desktop = window.matchMedia("(min-width: 1024px)");

  const setOpen = (drawer, open) => {
    // Drawers marked data-inline sit in the layout on desktop and stay usable there.
    const inline = drawer.dataset.inline !== undefined && desktop.matches;
    drawer.dataset.open = String(open);
    if (inline) drawer.removeAttribute("aria-hidden");
    else drawer.setAttribute("aria-hidden", String(!open));
    if ("inert" in drawer) drawer.inert = !open && !inline;
    const scrim = document.querySelector(`[data-scrim="${drawer.id}"]`);
    if (scrim) scrim.dataset.open = String(open);
    document.querySelectorAll(`[data-drawer-open="${drawer.id}"]`).forEach((b) =>
      b.setAttribute("aria-expanded", String(open))
    );
    document.documentElement.classList.toggle("overflow-hidden", open && !inline);
    if (inline) return;
    if (open) {
      lastFocus = document.activeElement;
      requestAnimationFrame(() => drawer.querySelector("[data-autofocus], a, button, input, select")?.focus());
    } else {
      lastFocus?.focus?.();
    }
  };

  document.querySelectorAll(".drawer[id]").forEach((d) => setOpen(d, false));

  document.addEventListener("click", (e) => {
    const opener = e.target.closest("[data-drawer-open]");
    if (opener) {
      const d = document.getElementById(opener.dataset.drawerOpen);
      if (d) setOpen(d, d.dataset.open !== "true");
      return;
    }
    const closer = e.target.closest("[data-drawer-close], [data-scrim]");
    if (closer) {
      const id = closer.dataset.drawerClose || closer.dataset.scrim || closer.closest(".drawer")?.id;
      const d = id && document.getElementById(id);
      if (d) setOpen(d, false);
    }
  });

  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    document.querySelectorAll('.drawer[data-open="true"]').forEach((d) => setOpen(d, false));
  });

  // Crossing the desktop breakpoint resets drawers and re-evaluates inline ones.
  desktop.addEventListener("change", () => {
    document.querySelectorAll(".drawer[id]").forEach((d) => {
      if (d.dataset.open === "true" || d.dataset.inline !== undefined) setOpen(d, false);
    });
  });

  return { setOpen };
}

/* Accordions (mobile nav sections). */
function initAccordions() {
  document.querySelectorAll("[data-accordion]").forEach((btn) => {
    btn.addEventListener("click", () => {
      btn.setAttribute("aria-expanded", String(btn.getAttribute("aria-expanded") !== "true"));
    });
  });
}

/* Banner carousel: Super Admin banners rotate; pause on hover, focus, or the button. */
export function initCarousel(root) {
  // Restartable: home-content.js rebuilds the slides from live banners and calls this again.
  root._carousel?.destroy();
  const ac = new AbortController();
  const on = (el, type, fn, opts = {}) => el?.addEventListener(type, fn, { ...opts, signal: ac.signal });
  const slides = [...root.querySelectorAll(".slide")];
  const dots = [...root.querySelectorAll("[data-goto]")];
  const toggle = root.querySelector("[data-carousel-toggle]");
  const live = root.querySelector("[data-carousel-live]");
  const ms = Number(root.dataset.interval || 7000);
  root.style.setProperty("--slide-ms", `${ms}ms`);
  let index = 0;
  let timer;
  let userPaused = reduceMotion;
  let hoverPaused = false;

  const schedule = () => {
    clearTimeout(timer);
    const paused = userPaused || hoverPaused || slides.length < 2;
    root.classList.toggle("is-paused", paused);
    if (!paused) timer = setTimeout(() => show(index + 1), ms);
  };
  const show = (i) => {
    index = (i + slides.length) % slides.length;
    slides.forEach((s, n) => {
      s.setAttribute("aria-hidden", String(n !== index));
      if ("inert" in s) s.inert = n !== index;
    });
    dots.forEach((d, n) => {
      d.setAttribute("aria-current", String(n === index));
      // restart the progress fill
      const bar = d.querySelector("span");
      if (bar) { bar.style.animation = "none"; void bar.offsetWidth; bar.style.animation = ""; }
    });
    if (live) live.textContent = `Slide ${index + 1} of ${slides.length}`;
    schedule();
  };
  const syncToggle = () => {
    if (!toggle) return;
    toggle.setAttribute("aria-label", userPaused ? "Play banner rotation" : "Pause banner rotation");
    toggle.querySelector("use")?.setAttribute("href", `/assets/img/icons.svg#i-${userPaused ? "play" : "pause"}`);
  };

  dots.forEach((d) => on(d, "click", () => show(Number(d.dataset.goto))));
  on(root.querySelector("[data-prev]"), "click", () => show(index - 1));
  on(root.querySelector("[data-next]"), "click", () => show(index + 1));
  on(toggle, "click", () => { userPaused = !userPaused; syncToggle(); schedule(); });
  on(root, "mouseenter", () => { hoverPaused = true; schedule(); });
  on(root, "mouseleave", () => { hoverPaused = false; schedule(); });
  on(root, "focusin", () => { hoverPaused = true; schedule(); });
  on(root, "focusout", (e) => { if (!root.contains(e.relatedTarget)) { hoverPaused = false; schedule(); } });
  on(document, "visibilitychange", () => { hoverPaused = document.hidden; schedule(); });

  // Swipe on touch screens
  let x0 = null;
  on(root, "touchstart", (e) => { x0 = e.touches[0].clientX; }, { passive: true });
  on(root, "touchend", (e) => {
    if (x0 === null) return;
    const dx = e.changedTouches[0].clientX - x0;
    if (Math.abs(dx) > 48) show(index + (dx < 0 ? 1 : -1));
    x0 = null;
  });

  syncToggle();
  show(0);
  root._carousel = { destroy: () => { ac.abort(); clearTimeout(timer); } };
}

function initCarousels() {
  document.querySelectorAll("[data-carousel]").forEach(initCarousel);
}

/* Tabs with arrow-key support. */
export function initTabs(root = document) {
  root.querySelectorAll('[role="tablist"]').forEach((list) => {
    const tabs = [...list.querySelectorAll('[role="tab"]')];
    const select = (tab, focus = true) => {
      tabs.forEach((t) => {
        const on = t === tab;
        t.setAttribute("aria-selected", String(on));
        t.tabIndex = on ? 0 : -1;
        const panel = document.getElementById(t.getAttribute("aria-controls"));
        if (panel) panel.hidden = !on;
      });
      if (focus) tab.focus();
      tab.scrollIntoView({ block: "nearest", inline: "nearest", behavior: reduceMotion ? "auto" : "smooth" });
    };
    tabs.forEach((t, i) => {
      t.addEventListener("click", () => select(t, false));
      t.addEventListener("keydown", (e) => {
        const step = { ArrowRight: 1, ArrowLeft: -1 }[e.key];
        if (step) { e.preventDefault(); select(tabs[(i + step + tabs.length) % tabs.length]); }
        if (e.key === "Home") { e.preventDefault(); select(tabs[0]); }
        if (e.key === "End") { e.preventDefault(); select(tabs.at(-1)); }
      });
    });
  });
}

/* Preview notice: remembered per browser; works without storage too. */
function initPreviewNotice() {
  const bar = document.querySelector("[data-preview-notice]");
  if (!bar) return;
  try { if (localStorage.getItem("ncit-preview-dismissed") === "1") bar.hidden = true; } catch {}
  bar.querySelector("button")?.addEventListener("click", () => {
    bar.hidden = true;
    try { localStorage.setItem("ncit-preview-dismissed", "1"); } catch {}
  });
}

/* Sticky header gains a shadow once the page scrolls. */
function initHeaderShadow() {
  const header = document.querySelector("[data-sticky-header]");
  if (!header) return;
  const sentinel = document.createElement("div");
  sentinel.setAttribute("aria-hidden", "true");
  header.before(sentinel);
  new IntersectionObserver(([entry]) => {
    header.classList.toggle("shadow-[0_8px_24px_-12px_rgb(16_31_92/0.25)]", !entry.isIntersecting);
  }).observe(sentinel);
}

/* In-page section nav highlights the section in view (department page).
   Exported so pages that render their sections later can call it again. */
let spy;
export function initScrollSpy() {
  const nav = document.querySelector("[data-scrollspy]");
  spy?.disconnect();
  if (!nav) return;
  const links = [...nav.querySelectorAll('a[href^="#"]')];
  const byId = new Map(links.map((a) => [a.getAttribute("href").slice(1), a]));
  const io = (spy = new IntersectionObserver(
    (entries) => {
      entries.forEach((en) => {
        if (!en.isIntersecting) return;
        links.forEach((a) => a.removeAttribute("aria-current"));
        const link = byId.get(en.target.id);
        if (link) {
          link.setAttribute("aria-current", "true");
          link.scrollIntoView({ block: "nearest", inline: "center", behavior: "auto" });
        }
      });
    },
    { rootMargin: "-30% 0px -60% 0px" }
  ));
  byId.forEach((_, id) => { const el = document.getElementById(id); if (el) io.observe(el); });
}

/* Mark the current top-level section in the main nav. */
function initCurrentSection() {
  const section = document.body.dataset.section;
  if (section) document.querySelectorAll(`[data-section="${section}"]:not(body)`).forEach((el) => el.setAttribute("aria-current", "page"));
}

/* Notification bell: only loaded when someone may be signed in (the readable CSRF cookie exists). */
function initBell() {
  if (!document.querySelector("[data-bell]") || !document.cookie.split("; ").some((c) => c.startsWith("ncit_csrf="))) return;
  import("./notifications.js").then((m) => m.mountAll()).catch(() => { /* the bell is optional */ });
}

export function init() {
  initCurrentSection();
  initPhotos();
  initMegaMenus();
  const drawers = initDrawers();
  initAccordions();
  initCarousels();
  initTabs();
  initPreviewNotice();
  initHeaderShadow();
  initScrollSpy();
  initBell();
  return { drawers };
}

export const api = init();
