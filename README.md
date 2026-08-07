# imenbouzouita.com

Static site — plain HTML/CSS/JS, no framework, no build step at deploy time.
Content (copy, case studies, nav) lives in [`build.py`](build.py) and is generated
into static HTML files that GitHub Pages serves directly.

## Why no Astro/Vite

The brief left the framework choice open. This machine has no Node.js/npm
installed, so a Node-based framework wasn't viable here. Plain static
HTML/CSS/JS meets every requirement in the brief (fast, no bloat, GitHub
Pages-ready, no server) without needing any toolchain at all — if you'd
rather move to Astro later, the content structure in `build.py` (a list of
dicts per case study, a few template functions) maps directly onto Astro
content collections.

## Editing content

Don't hand-edit `index.html`, `work/*/index.html`, `terms.html`, `privacy.html`,
or `impressum.html` directly — they're generated. Edit `build.py` instead
(case study copy, nav links, capability pillars, legal text, etc.), then
regenerate:

```bash
python3 build.py
```

Requires only Python 3 (already on macOS by default) — no npm install.

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

Root-relative URLs (`/assets/...`, `/work/...`) are used throughout, so
preview via a local server rather than opening files directly:

```bash
python3 -m http.server 8000
```

Then open http://localhost:8000

## Deploying to GitHub Pages

1. Create a GitHub repo and push this project (this repo already has `git init` run, no commits yet):
   ```bash
   git add -A
   git commit -m "Initial site"
   git branch -M main
   git remote add origin <your-repo-url>
   git push -u origin main
   ```
2. In the repo's Settings → Pages, set the source to the `main` branch, `/ (root)` folder.
3. `CNAME` (already in the repo root, containing `imenbouzouita.com`) and
   `.nojekyll` (so GitHub doesn't run Jekyll over the static output) are
   already in place.
4. Point your domain's DNS at GitHub Pages (A records to GitHub's IPs, or a
   CNAME record to `<username>.github.io`) — see GitHub's "Managing a custom
   domain" docs for current IPs.
5. No CI/build step is needed — the committed HTML/CSS/JS is the deployed
   output. Re-run `python3 build.py` locally and commit whenever you change
   `build.py`.

## Structure

```
assets/css/style.css     design system: colors, type, layout, motion
assets/js/main.js        nav, scroll-reveal, parallax, custom cursor, contact form
build.py                 content + templates + generator (source of truth)
index.html               generated
work/<slug>/index.html   generated, one per case study
terms.html, privacy.html, impressum.html   generated
```
