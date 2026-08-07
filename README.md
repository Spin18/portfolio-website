# imenbouzouita.com

Static site — plain HTML/CSS/JS, no framework, no build step at deploy time.
Bilingual (English + German). Copy lives in `content/en.json` and
`content/de.json`; [`build.py`](build.py) reads both and generates static
HTML files that GitHub Pages serves directly.

## Why no Astro/Vite

The brief left the framework choice open. This machine has no Node.js/npm
installed, so a Node-based framework wasn't viable here. Plain static
HTML/CSS/JS meets every requirement in the brief (fast, no bloat, GitHub
Pages-ready, no server) without needing any toolchain at all — if you'd
rather move to Astro later, the content structure in `build.py` (a list of
dicts per case study, a few template functions) maps directly onto Astro
content collections.

## Editing content

Don't hand-edit `index.html`, `work/*/index.html`, `terms.html`,
`privacy.html`, `impressum.html`, or anything under `de/` — they're all
generated. Edit `content/en.json` (copy, case studies, nav labels, legal
text, etc.) — or `content/de.json` for German — then regenerate:

```bash
python3 build.py
```

Requires only Python 3 (already on macOS by default) — no npm install.
Structural changes (new sections, new templates) go in `build.py`; wording
changes go in the JSON files.

## Languages (EN / DE)

The site is generated twice from the same templates in `build.py`: once
from `content/en.json` at the site root, once from `content/de.json` under
`/de/`. Every page has a small EN/DE switcher in the nav that links to the
equivalent page in the other language, plus `hreflang` tags in `<head>`
and sitemap entries for both, so search engines treat them as language
variants of the same content rather than duplicates.

**`content/de.json` currently mirrors `content/en.json` word-for-word** —
it's a structural placeholder, not a translation. To add the real German
copy:

1. Open `content/de.json`.
2. Replace the string values with German text — keep every key name and
   the overall structure (arrays, nested objects) identical to
   `content/en.json`, since `build.py` reads both by key.
3. The `impressum` entry is already in German in both files (legally
   required regardless of site language) — no change needed there.
4. Remove the top-level `"_translation_status"` key once translation is
   done (purely a note to self; `build.py` ignores it).
5. Rerun `python3 build.py` and commit the regenerated `de/` output
   alongside `content/de.json`.

The contact form's status messages (sent/error/sending/etc.) are also
localized — they're read from `content/*.json` → `contact.form` and passed
into the page as `data-msg-*` attributes that `assets/js/main.js` reads at
submit time, so those will pick up your German text automatically too.

## Before going live

- **Formspree**: create a form at formspree.io and replace `FORMSPREE_ACTION`
  near the top of `build.py` with your real endpoint, then rerun `build.py`.
- **Assets**: portrait (`imen-portrait.jpg`/`.webp`), hero background texture
  (`texture-bg.jpg`/`.webp` + mobile variants), and your signature
  (`logos/logo.png`, used in the About section) are wired in and optimized.
  Still placeholder:
  - Client logos for the trust strip (currently text wordmarks — swap the
    `.trust-logo` spans for `<img>` tags once you have real logo files)
  - A cover image per case study (currently a placeholder block in
    `build_case_study()`)
  - `assets/img/og-cover.jpg` — currently a generated placeholder social
    share image; swap for a real one if you want a custom preview card
- **Legal pages**: `impressum.html` now uses your real registration details
  (pulled from imenbouzouita.com/impressum). `terms.html` and `privacy.html`
  are still placeholders — have them reviewed before launch (GDPR for the
  Privacy Policy).
- **Calendly / contact**: the Calendly link and Formspree form are the two
  live integrations — double check both before sharing the site.

## Local preview

All internal links and asset paths are relative (computed per-page from
real file paths, not hardcoded), so the site works when opened directly
from disk too — but a local server is still recommended since that's how
it'll actually be served:

```bash
python3 -m http.server 8000
```

Then open http://localhost:8000 (English) or http://localhost:8000/de/
(German).

## Deploying to GitHub Pages

Live at: https://github.com/Spin18/portfolio-website, currently served at
https://spin18.github.io/portfolio-website/ (no custom domain wired up yet
— the `CNAME` file was removed while testing on the raw `github.io` URL).
All internal links and asset paths are relative, so the site works
correctly at any hosting depth — this subpath, a custom domain root, or a
local preview — without changes.

1. In the repo's Settings → Pages, source is the `main` branch, `/ (root)`
   folder.
2. `.nojekyll` is in place so GitHub doesn't run Jekyll over the static
   output.
3. **When ready to switch to the imenbouzouita.com domain**: add a `CNAME`
   file back to the repo root containing `imenbouzouita.com`, then point
   the domain's DNS at GitHub Pages (A records to GitHub's IPs, or a CNAME
   record to `spin18.github.io`) — see GitHub's "Managing a custom domain"
   docs for current IPs.
4. No CI/build step is needed — the committed HTML/CSS/JS is the deployed
   output. Re-run `python3 build.py` locally and commit whenever you change
   `build.py`.

## Structure

```
content/en.json, content/de.json   all page copy, per language — edit these
build.py                           templates + generator (source of truth for markup)
assets/css/style.css               design system: colors, type, layout, motion
assets/js/main.js                  nav, scroll-reveal, parallax, custom cursor, contact form
index.html                         generated (English home)
work/<slug>/index.html             generated, one per case study (English)
terms.html, privacy.html, impressum.html   generated (English)
de/index.html                      generated (German home)
de/work/<slug>/index.html          generated (German)
de/terms.html, de/privacy.html, de/impressum.html   generated (German)
```
