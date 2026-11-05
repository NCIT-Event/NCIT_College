---
name: NCIT Website
description: Classic university website for Nepal College of Information Technology, in the emblem's royal blue and Om red.
colors:
  brand-950: "#0a1440"
  brand-900: "#101f5c"
  brand-800: "#182c85"
  brand-700: "#2140a6"
  brand-600: "#2d53c4"
  brand-200: "#c5d1f2"
  brand-100: "#e4eaf9"
  brand-50: "#f2f5fc"
  om-700: "#a8131c"
  om-600: "#cf1f29"
  om-50: "#fdeced"
  sky-500: "#2f97d3"
  sky-300: "#8fcdef"
  leaf-700: "#1f6b2e"
  leaf-50: "#e8f5ea"
  amber-700: "#8a5a00"
  amber-50: "#fdf3dc"
  ink: "#11163a"
  ink-2: "#454c6e"
  ink-3: "#5c6382"
  line: "#d8ddeb"
  line-2: "#e9ecf4"
  paper: "#ffffff"
  canvas: "#f6f7fb"
typography:
  display:
    fontFamily: "Source Serif 4, Georgia, serif"
    fontSize: "clamp(2.5rem, 1.6rem + 3.6vw, 5rem)"
    fontWeight: 600
    lineHeight: 1.02
    letterSpacing: "-0.025em"
  h1:
    fontFamily: "Source Serif 4, Georgia, serif"
    fontSize: "clamp(2.125rem, 1.6rem + 2.2vw, 3.5rem)"
    fontWeight: 600
    lineHeight: 1.06
    letterSpacing: "-0.02em"
  h2:
    fontFamily: "Source Serif 4, Georgia, serif"
    fontSize: "clamp(1.75rem, 1.4rem + 1.4vw, 2.625rem)"
    fontWeight: 600
    lineHeight: 1.1
    letterSpacing: "-0.015em"
  h3:
    fontFamily: "Source Serif 4, Georgia, serif"
    fontSize: "clamp(1.25rem, 1.1rem + 0.5vw, 1.5rem)"
    fontWeight: 600
    lineHeight: 1.25
  body:
    fontFamily: "Mukta, system-ui, sans-serif"
    fontSize: "1.0625rem"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "Mukta, system-ui, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 600
    letterSpacing: "0.06em"
rounded:
  sm: "3px"
  md: "6px"
  lg: "10px"
spacing:
  gutter-mobile: "16px"
  gutter-tablet: "24px"
  gutter-desktop: "40px"
  section-mobile: "64px"
  section-desktop: "96px"
components:
  button-apply:
    backgroundColor: "{colors.om-600}"
    textColor: "{colors.paper}"
    rounded: "{rounded.sm}"
    padding: "0 20px"
    height: "44px"
  button-apply-hover:
    backgroundColor: "{colors.om-700}"
  button-primary:
    backgroundColor: "{colors.brand-800}"
    textColor: "{colors.paper}"
    rounded: "{rounded.sm}"
    padding: "0 20px"
    height: "44px"
  button-primary-hover:
    backgroundColor: "{colors.brand-900}"
  button-outline:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "0 20px"
    height: "44px"
  tag:
    backgroundColor: "{colors.brand-50}"
    textColor: "{colors.brand-800}"
    rounded: "{rounded.sm}"
    padding: "2px 8px"
  field:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "0 12px"
    height: "44px"
  sample-marker:
    backgroundColor: "{colors.amber-50}"
    textColor: "{colors.amber-700}"
    rounded: "{rounded.sm}"
    padding: "1px 6px"
---

# Design System: NCIT Website

## Overview

**Creative North Star: "The Well-Kept Institution"**

A classic university website, played straight at the craft level of harvard.edu and mit.edu: a photography-led banner, clear mega-menus, editorial news, events and notices, leadership messages, and an apply band. NCIT's identity comes from its emblem. Royal blue is the institution, Om red is the call to apply, and sky blue is a quiet accent on dark grounds. Everything else is white, a cool canvas grey, and thin rules.

The system serves three modes. The public site persuades a prospective student on a phone. Department pages are read top to bottom. The dashboard is a tool used daily by content owners. All three share tokens and components. Dashboards add density and drop the editorial serif scale except for page titles.

**Key Characteristics:**
- Serif display (Source Serif 4, optical sizes) over a humanist sans (Mukta, Devanagari-ready for a Nepali toggle).
- Divided lists and 1px rules instead of card grids.
- Red is reserved for Apply and destructive or urgent states.
- Every photo is a named slot under `assets/img/photos/`, with a labelled placeholder until the real file exists.
- Invented content always carries the amber Sample marker.

## Colors

### Primary
- **Royal Blue** (`brand-800` #182c85): the institutional colour, sampled from the emblem's star. Primary buttons, the apply band, links (`brand-700`), active states.
- **Midnight** (`brand-950` #0a1440): utility bar, footer, dashboard sidebar.

### Secondary
- **Om Red** (`om-600` #cf1f29): sampled from the Om in the emblem. Only for Apply actions, urgent alerts, destructive actions and exam notices.

### Tertiary
- **Sky** (`sky-300` #8fcdef, `sky-500` #2f97d3): from the globe and ribbon. Accents on dark grounds: step numbers, active dashboard icons, focus rings on dark.

### Neutral
- **Ink** (`ink` #11163a), **Ink 2** (#454c6e) for secondary text, **Ink 3** (#5c6382) for meta text (meets 4.5:1 on canvas and white).
- **Paper** (#ffffff) page ground, **Canvas** (#f6f7fb) alternating section ground, **Line** (#d8ddeb) and **Line 2** (#e9ecf4) rules.
- Status: **Leaf** (green, from the globe's land) for active and holiday, **Amber** for invited, result and sample markers.

### Named Rules
**The Red Means Apply Rule.** Om red appears only on Apply buttons, urgent banners, destructive actions and exam tags. Never as decoration or a section ground.

**The Brand Lives in One File Rule.** Brand hexes are estimated from the emblem image until the college confirms them; every page reads them from the `@theme` block in `frontend/src/css/site.css`, so confirming them is a one-file change.

## Typography

**Display Font:** Source Serif 4 (variable, optical sizing), self-hosted
**Body Font:** Mukta 400/500/600/700, self-hosted

### Hierarchy
- **Display** (600, clamp 2.5–5rem, 1.02): hero banner headlines only.
- **H1** (600, clamp 2.125–3.5rem): page titles (department name, apply band).
- **H2** (600, clamp 1.75–2.625rem): section titles.
- **H3** (600, clamp 1.25–1.5rem): department names in lists, sub-sections.
- **Body** (400, 1.0625rem/1.6): measure capped near 62–66ch; lead paragraphs 1.125–1.25rem.
- **Label** (600, 0.8125rem, +0.06em, uppercase): mega-menu column headings, table headers, dashboard nav groups only. Never above a heading.

### Named Rules
**The Serif Speaks First Rule.** Headings are serif and sentence case; UI, meta and body text are Mukta. Dashboards use the serif only for the page title.

## Layout

- Container `.wrap`: max 84rem, gutters 16 / 24 / 40px at mobile / sm / lg.
- Sections `.section`: 64px vertical on mobile, 96px from md; alternate Paper and Canvas grounds, or separate with a 1px top rule.
- Grid: 12 columns on desktop; editorial splits of 7/5 or 8/4; lists in two columns from md.
- Breakpoints: Tailwind defaults (sm 640, md 768, lg 1024, xl 1280). Header nav and mega-menus appear from lg; below that, a right-side drawer.
- Touch targets at least 44px (`min-h-11`).

## Elevation & Depth

Flat by default. Depth appears only on surfaces that float: the sticky header gains a soft shadow after scroll, and mega-menus, drawers and sheets use `--shadow-menu` (`0 2px 4px rgb(16 31 92 / .06), 0 24px 48px -12px rgb(16 31 92 / .28)`). No shadows on content blocks.

## Shapes

3px corners (`rounded.sm`) on buttons, tags, fields and photos; 6px on dashboard panels and testimonial blocks; full circles only for avatars and the lettermark fallback.

## Components

### Buttons
- **Apply** (`.btn-apply`): Om red, white text, 44px tall, 3px corners. One per view in the header plus contextual Apply actions.
- **Primary** (`.btn-primary`): royal blue. **Light** (`.btn-light`) and **Outline light** on dark grounds. **Outline** on light grounds. **Ghost** for icon buttons.
- Press: 1px down on active; transitions use `--ease-out-expo`.

### Chips
- **Tag** (`.tag`, `.tag-om`, `.tag-leaf`, `.tag-amber`): 13px semibold on a tint; categories, roles with scope, statuses.
- **Sample marker** (`.sample`): 11px uppercase amber chip placed after any invented content.

### Cards / Containers
Cards are avoided. Content sits in divided lists (`.divided`), definition lists with rules, and editorial splits. Exceptions: testimonial blocks on Canvas, and bordered white panels in the dashboard.

### Inputs / Fields
`.field`: 44px, 1px Line border, 3px corners; hover darkens the border; focus shows a royal-blue border plus a 3px soft ring. Errors: Om-700 message below the field with `role="alert"` and `aria-invalid`.

### Navigation
- Utility bar (Midnight): audience links and Sign in.
- Main header (white, sticky, blurred): lettermark/emblem, wordmark (hidden below 640px), six items with a 3px royal-blue underline that grows from the left on hover, open or current.
- Mega-menus: three columns plus a feature panel with a photo slot.
- Mobile: right drawer with accordions and a fixed Sign in / Apply footer.
- Dashboard: Midnight sidebar with grouped links filtered by role; the current link uses a lighter fill and a sky-blue icon.

### Photo slot (signature)
`.photo` wraps an `<img>` pointing at its intended file. While the file is missing, JS adds `.is-missing` and a white "Photo to come" label shows on a pale blue field (`.photo-dark` for the hero: navy with a soft sky glow).

### Banner carousel (signature)
Super Admin banners: full-bleed photo, bottom gradient scrim, serif display headline, two actions. Rotation every 7s with progress bars, pause/play, previous/next, swipe, pause on hover and focus, and no autoplay under reduced motion. Copy rises in sequence; the photo pushes in slowly.

## Do's and Don'ts

### Do:
- **Do** take brand colours from the tokens; never hard-code hexes in pages.
- **Do** mark every invented name, date, figure, quote and photo with the Sample marker.
- **Do** give every image an intended file path and alt text, so real photos drop in without code changes.
- **Do** keep Om red for Apply, urgent and destructive actions.
- **Do** use divided lists and rules for collections of items.

### Don't:
- **Don't** put a small uppercase label above a heading.
- **Don't** use coloured side bars thicker than 1px on list items, nav links or callouts.
- **Don't** build pages from grids of identical icon cards.
- **Don't** redraw or restyle the NCIT emblem; use the supplied file.
- **Don't** present invented statistics (placement rates, rankings, student counts) as fact.
