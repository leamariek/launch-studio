---
name: brand-intake
description: Extracts a project's real design system (colors, typography, radii, spacing, shadows, motion curves, logo, fonts) from its code into brand.json, and builds the rebuild kit a coded launch video draws from: font files, verbatim copy, real data, map and chart geometry, and faithful canvas components of the product's UI, checked side by side against the live product. Use this whenever a launch video, motion piece, animated visual, or marketing asset must match an existing product's design, when the user points at a Tailwind config, CSS tokens, Figma file, or brand guide, or says "in our design" or "on-brand."
---

# Brand Intake

Your job is fidelity. The video must look like it was made by the product's own design team on their best day. You extract and rebuild; you do not invent.

## Step 1: Find the sources

Search the project in this priority order and record every file used:
1. Design tokens: `tokens.json`, `*.tokens.json`, Style Dictionary output, CSS custom properties in `:root`.
2. Tailwind or framework theme: `tailwind.config.*`, `@theme` blocks, theme providers (MUI, Chakra, shadcn `globals.css`).
3. Component library styles: buttons, cards, inputs. They reveal radii, shadows, borders.
4. Fonts: `@font-face` rules, `next/font` calls, `public/fonts`, Google Fonts links.
5. Logo and marks: `public/`, `assets/`, favicon, SVGs in components.
6. Motion: existing CSS transitions, Framer Motion variants, easing constants.
7. Brand guide or Figma (if the user provides them). Figma overrides code only when the user says so.
8. **The live site, when the code is not local.** Fetch the page and its CSS chunks (`/_next/static/...css` and similar). Take tokens from `:root` and module rules, texture filters (for example an SVG `feTurbulence` grain with its blend mode and opacity), background gradients, and the woff2 files the site actually serves. These are the real production values, so they count as sources.

## Step 2: Write `launch/03-brand/brand.json`

```json
{
  "source_files": ["app/src/styles/tokens.css", "tailwind.config.ts"],
  "mode": "dark",
  "color": {
    "bg": "#0B0B0F", "surface": "#15151C", "text": "#F4F4F6", "muted": "#8A8A99",
    "accent": "#4F7BFF", "accent_2": null, "success": "#2BC48A", "danger": "#F2555A"
  },
  "type": {
    "display": { "family": "Söhne", "weights": [500, 700], "tracking": "-0.02em", "file": "kit/fonts/sohne.woff2" },
    "body": { "family": "Söhne", "weights": [400], "tracking": "0" },
    "mono": { "family": "JetBrains Mono", "weights": [400] }
  },
  "radius": { "sm": 6, "md": 10, "lg": 16, "pill": 999 },
  "shadow": { "card": "0 1px 0 rgba(255,255,255,.04) inset, 0 8px 24px rgba(0,0,0,.4)" },
  "spacing_unit": 4,
  "motion": {
    "ease_standard": "cubic-bezier(0.2, 0, 0, 1)",
    "ease_emphasis": "cubic-bezier(0.3, 0, 0, 1.2)",
    "duration_base_ms": 240
  },
  "logo": { "full": "kit/logo.svg", "mark": "kit/mark.svg", "min_clearspace": "0.5x mark height" },
  "personality": ["precise", "calm", "confident"],
  "do": ["generous negative space", "single accent per frame"],
  "dont": ["gradients (the product uses none)", "drop shadows on text"]
}
```

Every value must trace to a source file. If a value doesn't exist in the project (for example no motion tokens), derive it from the product's actual behavior, mark it `"derived": true` with a note, and flag it for the user. Never fill gaps with generic defaults silently.

`personality`, `do`, and `dont` come from observing the product and landing page, not from adjectives you like.

## Step 3: Build the rebuild kit (`launch/03-brand/kit/`)

The video draws the product in code (see `launch-film/references/reference-films.md`). The kit is what makes that drawing faithful instead of invented.

- **Inventory first.** Read the UI code and list every component, motion and state with file:line (`inventory/*.md`): what it looks like, how it moves (trigger, values, duration, ease), what copy and data it shows. Mark what is live on the site and what is dead code; the video uses only what is live.
- **Fonts.** The woff2 files the product actually uses, in `kit/fonts/` (check the license; OFL fonts from Google Fonts are fine). Every weight the video needs.
- **Copy.** `kit/copy.json`: every string the video may show, verbatim, with its source file and line.
- **Data.** `kit/data/*.json`: the real records behind lists, counts and statuses (for example programs, per-country counts, status keys), extracted by script, never by eye.
- **Geometry.** `kit/geo/*`: SVG paths, viewBox and projection for maps and charts, straight from the source.
- **Components.** `kit/components.js`: canvas draw functions for the product's UI parts (a button, a tab, a list row, a seal, a chat window), taking a state and a progress value, built from brand.json tokens and the inventory's exact values. Simplify only by leaving things out, never by changing them.
- **Fidelity check.** Screenshot the real UI at 2x (Playwright) and render each component at the same size; put them side by side in `kit/fidelity.png` and fix every visible difference in colour, radius, type, spacing. Screenshots live in `kit/reference/` for this check only; they never appear in the video.

## Step 4: Verify

Render `kit/specimen.html`: palette swatches with hex values, type scale at display and body sizes, radius and shadow samples, the logo or wordmark, and every component in its key states. Screenshot to `kit/specimen.png` and show it. A wrong font caught here saves 1,300 frames.

## Sensitive data

Before any screenshot is saved, check for real customer names, emails, API keys, and internal URLs. Replace with seed data in the app, then recapture. Blur is a last resort and must be noted in the kit README.
