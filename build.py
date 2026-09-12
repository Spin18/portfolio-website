#!/usr/bin/env python3
"""Static site generator for imenbouzouita.com.

No framework, no npm — just Python stdlib templating so the header/footer/
case-study template stay DRY while the deployed output is plain static
HTML/CSS/JS (GitHub Pages needs no build step at request time).

Bilingual (EN/DE): all page copy lives in content/en.json and
content/de.json — same structure, different strings. English is served
from the site root; German from /de/. Every internal link (nav, footer,
case-study prev/next, the language switcher, asset paths) is computed
with `href_to()`, which resolves a real relative path between any two
generated files, so it's correct regardless of language prefix or
nesting depth. To add real German copy, edit content/de.json (keep the
same keys as en.json) and rerun this script.

Run: python3 build.py
"""
import datetime
import hashlib
import json
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))
SITE_URL = "https://www.imenbouzouita.com"
CALENDLY = "https://calendly.com/imenbouzouita/1-1-discovery-call"
LINKEDIN_URL = "https://www.linkedin.com/in/imen-bouzouita-b65051107/"
INSTAGRAM_URL = "https://www.instagram.com/ima_gi_n/"
FORMSPREE_ACTION = "https://formspree.io/f/xdenkldz"
# Replace with the real Measurement ID from analytics.google.com (Admin >
# Data Streams > your stream). GA4 is never loaded until a visitor accepts
# the cookie banner — see the consent logic in assets/js/main.js.
GA4_MEASUREMENT_ID = "G-G78M71MS8D"
# Cloudflare Web Analytics: cookieless, no persistent identifiers, so unlike
# GA4 it loads unconditionally — it isn't gated behind the cookie banner
# because it doesn't need consent under GDPR/ePrivacy in the first place.
CLOUDFLARE_ANALYTICS_TOKEN = "66edec62f8284619abfb73b524995fad"
# Contentsquare: session recordings/heatmaps tied to real visitor behaviour —
# this IS personal data, so unlike Cloudflare Web Analytics it's gated behind
# the same cookie-banner "Analytics" consent as GA4. See assets/js/main.js.
CONTENTSQUARE_SRC = "https://t.contentsquare.net/uxa/eebaa999b0989.js"
# font-display=optional: browser waits ~100ms max for the font, then commits
# to whichever (fallback or webfont) is ready and never swaps later — this is
# what avoids CLS. Loaded non-blocking via the media="print" swap trick below,
# so it never holds up first paint either.
FONTS_URL = "https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,500;0,9..144,600;0,9..144,700;1,9..144,500&family=Inter:wght@400;500;600;700&display=optional"

# Cache-busting query param for main.js: browsers cache external scripts
# aggressively (unlike our CSS, which is inlined and sidesteps this
# entirely), so without this, a visitor with a warm cache could keep
# running stale JS after a deploy until their cache happens to expire.
with open(os.path.join(ROOT, "assets/js/main.js"), "rb") as _f:
    MAIN_JS_VERSION = hashlib.md5(_f.read()).hexdigest()[:8]

TRUST_LOGOS = [
    {"name": "Siemens", "file": "siemens.svg", "w": 1200, "h": 800},
    {"name": "BMW", "file": "bmw.webp", "w": 76, "h": 76},
    {"name": "Deloitte", "file": "deloitte.svg", "w": 2500, "h": 543},
    {"name": "innogy", "file": "innogy.svg", "w": 442, "h": 652},
    {"name": "und gretel", "file": "und-gretel.svg", "w": 152, "h": 84},
    {"name": "BaliSpirit", "file": "balispirit.webp", "w": 76, "h": 76},
    {"name": "yogabarn", "file": "yogabarn.webp", "size": "lg", "w": 109, "h": 116},
    {"name": "Rikepa", "file": "rikepa.webp", "w": 76, "h": 75},
]

LANGUAGES = [
    {"code": "en", "dir": "", "label": "EN"},
    {"code": "de", "dir": "de/", "label": "DE"},
]

# og:locale needs a language_TERRITORY tag, not the bare "en"/"de" used
# elsewhere (html lang, hreflang). en_US as the neutral default for
# undifferentiated English content (no single English-speaking market is
# targeted); de_DE matches the business's actual Berlin address.
OG_LOCALE = {"en": "en_US", "de": "de_DE"}

def _nav_entries(t, current_path):
    lang_code = _lang_of(current_path)
    home = href_to(current_path, lang_home_path(lang_code))
    resources_href = href_to(current_path, lang_resources_index_path(lang_code))
    return [
        (t["nav"]["what_i_do"], f"{home}#work-do"),
        (t["nav"]["case_studies"], f"{home}#work"),
        (t["nav"]["resources"], resources_href),
        (t["nav"]["about"], f"{home}#about"),
        (t["nav"]["faq"], f"{home}#faq"),
        (t["nav"]["contact"], f"{home}#contact"),
    ]


def load_content():
    content = {}
    for lang in LANGUAGES:
        path = os.path.join(ROOT, "content", f"{lang['code']}.json")
        with open(path, encoding="utf-8") as f:
            content[lang["code"]] = json.load(f)
    return content


def href_to(current_path, target_path):
    """Relative href from the page at `current_path` to `target_path`.

    Both are repo-relative output paths (e.g. "work/slug/index.html",
    "de/index.html", "assets/css/style.css"). Using real relpath math
    instead of manually counting "../" means this is correct no matter
    how deep a page is nested or which language prefix it's under.
    """
    cur_dir = os.path.dirname(current_path)
    r = os.path.relpath(target_path, cur_dir or ".").replace(os.sep, "/")
    if r == "index.html":
        return "./"
    if r.endswith("/index.html"):
        return r[: -len("index.html")]
    return r


def asset_href(current_path, sub_path):
    """Relative href from `current_path` to assets/<sub_path>."""
    return href_to(current_path, f"assets/{sub_path}")


_IMAGE_SIZE_CACHE = {}


def image_size(sub_path):
    """Intrinsic (width, height) of assets/img/<sub_path>, read straight from
    the file's own header — stdlib only, no Pillow dependency for a one-line
    lookup. Covers exactly the two raster formats this site uses (JPEG,
    WebP); SVGs/PNGs are only ever used where dimensions are already known
    up front (TRUST_LOGOS' hardcoded w/h, the hand-set portrait/signature
    attributes), so they're not needed here."""
    if sub_path in _IMAGE_SIZE_CACHE:
        return _IMAGE_SIZE_CACHE[sub_path]

    with open(os.path.join(ROOT, "assets", "img", sub_path), "rb") as f:
        data = f.read()

    if data[:2] == b"\xff\xd8":
        i, n = 2, len(data)
        size = None
        while i < n:
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                height = (data[i + 5] << 8) + data[i + 6]
                width = (data[i + 7] << 8) + data[i + 8]
                size = (width, height)
                break
            length = (data[i + 2] << 8) + data[i + 3]
            i += 2 + length
        if size is None:
            raise ValueError(f"no JPEG SOF marker found in {sub_path}")
    elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        chunk_type = data[12:16]
        if chunk_type == b"VP8 ":
            width = (data[26] | (data[27] << 8)) & 0x3FFF
            height = (data[28] | (data[29] << 8)) & 0x3FFF
        elif chunk_type == b"VP8L":
            b0, b1, b2, b3 = data[21], data[22], data[23], data[24]
            width = 1 + (((b1 & 0x3F) << 8) | b0)
            height = 1 + (((b3 & 0xF) << 10) | (b2 << 2) | (b1 >> 6))
        elif chunk_type == b"VP8X":
            width = 1 + (data[24] | (data[25] << 8) | (data[26] << 16))
            height = 1 + (data[27] | (data[28] << 8) | (data[29] << 16))
        else:
            raise ValueError(f"unrecognised WebP chunk {chunk_type!r} in {sub_path}")
        size = (width, height)
    else:
        raise ValueError(f"unsupported image format for {sub_path}")

    _IMAGE_SIZE_CACHE[sub_path] = size
    return size


OG_COVER_W, OG_COVER_H = image_size("og-cover.jpg")


_CSS_TEMPLATE = None


_CSS_IMG_FILES = ["texture-bg-mobile.jpg", "texture-bg.jpg"]


def _load_css_template():
    """Read style.css once and cache it. Its url('../img/<file>') refs are
    left as per-file placeholders so inline_css() can substitute the correct
    relative path per page depth — the raw text can't be used as-is once
    it's embedded in HTML instead of served from assets/css/."""
    global _CSS_TEMPLATE
    if _CSS_TEMPLATE is None:
        with open(os.path.join(ROOT, "assets", "css", "style.css"), encoding="utf-8") as f:
            css = f.read()
        for fname in _CSS_IMG_FILES:
            css = css.replace(f"url('../img/{fname}')", f"url('__IMG_{fname}__')")
        _CSS_TEMPLATE = css
    return _CSS_TEMPLATE


def inline_css(current_path):
    """style.css content (6KB) inlined into <head>, with its background-image
    url()s rewritten to this page's correct relative path — eliminates the
    external stylesheet request from the critical rendering path entirely."""
    css = _load_css_template()
    for fname in _CSS_IMG_FILES:
        href = asset_href(current_path, f"img/{fname}")
        css = css.replace(f"__IMG_{fname}__", href)
    return css


def lang_home_path(lang_code):
    d = next(l["dir"] for l in LANGUAGES if l["code"] == lang_code)
    return f"{d}index.html"


def lang_case_study_path(lang_code, slug):
    d = next(l["dir"] for l in LANGUAGES if l["code"] == lang_code)
    return f"{d}work/{slug}/index.html"


def lang_legal_path(lang_code, slug):
    d = next(l["dir"] for l in LANGUAGES if l["code"] == lang_code)
    return f"{d}{slug}.html"


def lang_resources_index_path(lang_code):
    d = next(l["dir"] for l in LANGUAGES if l["code"] == lang_code)
    return f"{d}resources/index.html"


def lang_resource_path(lang_code, slug):
    d = next(l["dir"] for l in LANGUAGES if l["code"] == lang_code)
    return f"{d}resources/{slug}/index.html"


def lang_facts_path(lang_code):
    d = next(l["dir"] for l in LANGUAGES if l["code"] == lang_code)
    return f"{d}facts/index.html"


def _count_words(text):
    return len(re.sub("<[^>]+>", "", text).split())


def estimate_read_minutes(article):
    """~200 wpm, counted from the article's own section text (tags stripped)
    so a displayed reading time can never drift from the actual content."""
    word_count = 0
    for section in article["sections"]:
        for p in _as_list(section.get("body")):
            word_count += _count_words(p)
        for item in section.get("items", []):
            word_count += _count_words(item["heading"])
            for p in _as_list(item.get("body")):
                word_count += _count_words(p)
    return max(1, round(word_count / 200))


def _as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def meta_description(short, long, target=155):
    """A meta description built from a short tagline plus a longer summary
    — short taglines alone (a case study's one-liner) are too brief for a
    search snippet on their own, but always exist and are already good
    copy, so extend rather than replace them. Stops at a full sentence
    within the target length where one exists, else the last whole word,
    so it never cuts off mid-word."""
    short = short.rstrip(".!?")
    if len(short) >= target:
        return short[:target].rsplit(" ", 1)[0].rstrip(".,;:") + "…"

    combined = f"{short}. {long}"
    if len(combined) <= target:
        return combined

    truncated = combined[:target]
    last_period = truncated.rfind(". ")
    if last_period > len(short):
        return truncated[: last_period + 1]
    return truncated.rsplit(" ", 1)[0].rstrip(".,;:") + "…"


def _inline_to_markdown(text):
    """The only inline HTML this site's content ever uses is <strong>/<em>
    for emphasis — converted to real Markdown syntax rather than left as
    raw tags, since the whole point of a .md sibling is to hand agents
    clean text instead of markup to parse."""
    text = re.sub(r"<strong>(.*?)</strong>", r"**\1**", text)
    text = re.sub(r"<em>(.*?)</em>", r"*\1*", text)
    return text


def url_for(current_path):
    """Absolute canonical URL for a repo-relative output path."""
    if current_path.endswith("index.html"):
        p = current_path[: -len("index.html")]
        return f"{SITE_URL}/{p}" if p else f"{SITE_URL}/"
    return f"{SITE_URL}/{current_path}"


# Real, publicly-disclosed business address (from impressum.html —
# required by German law to be public) — used for structured data. Email
# and phone are also disclosed on the Impressum, but deliberately excluded
# here: both are obfuscated in the page's visible HTML specifically to
# block basic scrapers, and including them in structured data (never
# obfuscated, always machine-readable) would defeat that entirely. No
# pricing is included since it isn't disclosed anywhere on this site;
# adding it to structured data would be inaccurate.
BUSINESS_ADDRESS = {
    "@type": "PostalAddress",
    "streetAddress": "Mahlower Strasse 14",
    "postalCode": "12049",
    "addressLocality": "Berlin",
    "addressCountry": "DE",
}
BUSINESS_VAT_ID = "DE367654068"  # from impressum.html, § 27 a UStG
# Backfilled once for all existing case studies (they didn't carry a real
# publish date before this). Give a case study its own date here if/when
# one actually needs to differ.
CASE_STUDIES_DATE_PUBLISHED = "2026-08-28"


def _json_ld_script(graph):
    payload = json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False, indent=2)
    return f'<script type="application/ld+json">\n{payload}\n</script>'


def _core_entities(t, lang_code):
    """Person/ProfessionalService/WebSite nodes shared, by @id, across every
    page that references them (homepage, facts page). Keeping this in one
    place means the two JSON-LD graphs can never drift apart on the same
    real-world entity."""
    portrait_url = f"{SITE_URL}/assets/img/imen-portrait.jpg"

    person = {
        "@type": "Person",
        "@id": f"{SITE_URL}/#person",
        "name": "Imen Bouzouita",
        "jobTitle": "UX, CRO & Digital Strategy Consultant",
        "description": t["about"]["paragraphs"][0],
        "url": SITE_URL,
        "image": portrait_url,
        "address": BUSINESS_ADDRESS,
        "knowsLanguage": ["German", "English", "French", "Arabic"],
        "alumniOf": [
            {"@type": "CollegeOrUniversity", "name": "Technical University of Munich"},
            {"@type": "EducationalOrganization", "name": "Deloitte Neuroscience Institute"},
        ],
        "worksFor": {"@id": f"{SITE_URL}/#business"},
        "sameAs": [LINKEDIN_URL, INSTAGRAM_URL],
    }

    offers = [
        {
            "@type": "Offer",
            "itemOffered": {
                "@type": "Service",
                "name": cap["title"],
                "description": cap["pitch"],
            },
        }
        for cap in t["capabilities"]["items"]
    ]

    business = {
        "@type": "ProfessionalService",
        "@id": f"{SITE_URL}/#business",
        "name": "Imen Bouzouita — Digital Product, UX & CRO Consultant",
        "description": t["meta"]["site_description"],
        "url": SITE_URL,
        "image": portrait_url,
        "address": BUSINESS_ADDRESS,
        "vatID": BUSINESS_VAT_ID,
        "areaServed": "Worldwide",
        "founder": {"@id": f"{SITE_URL}/#person"},
        "knowsAbout": [
            "User Experience (UX) Design",
            "Conversion Rate Optimization (CRO)",
            "Search Engine Optimization (SEO)",
            "Landing Page Design",
            "A/B Testing",
            "Web Analytics",
        ],
        "makesOffer": offers,
        "sameAs": [LINKEDIN_URL, INSTAGRAM_URL],
    }

    website = {
        "@type": "WebSite",
        "@id": f"{SITE_URL}/#website",
        "url": SITE_URL,
        "name": t["meta"]["site_title"],
        "inLanguage": lang_code,
        "publisher": {"@id": f"{SITE_URL}/#business"},
    }

    return person, business, website


def build_json_ld_home(t, current_path):
    lang_code = _lang_of(current_path)
    person, business, website = _core_entities(t, lang_code)
    home_url = url_for(current_path)
    webpage = {
        "@type": "WebPage",
        "@id": f"{home_url}#webpage",
        "url": home_url,
        "name": t["meta"]["site_title"],
        "description": t["meta"]["site_description"],
        "inLanguage": lang_code,
        "isPartOf": {"@id": f"{SITE_URL}/#website"},
        "about": {"@id": f"{SITE_URL}/#business"},
    }

    faq_page = {
        "@type": "FAQPage",
        "@id": f"{home_url}#faq",
        "mainEntity": [
            {
                "@type": "Question",
                "name": item["q"],
                "acceptedAnswer": {"@type": "Answer", "text": item["a"]},
            }
            for item in t["faq"]["items"]
        ],
    }

    return _json_ld_script([website, webpage, person, business, faq_page])


def build_json_ld_facts(t, current_path):
    lang_code = _lang_of(current_path)
    person, business, website = _core_entities(t, lang_code)
    facts_url = url_for(current_path)

    webpage = {
        "@type": "AboutPage",
        "@id": f"{facts_url}#webpage",
        "url": facts_url,
        "name": t["grounding"]["heading"],
        "description": t["grounding"]["human_note"],
        "inLanguage": lang_code,
        "isPartOf": {"@id": f"{SITE_URL}/#website"},
        "mainEntity": {"@id": f"{SITE_URL}/#person"},
        "about": {"@id": f"{SITE_URL}/#business"},
    }

    faq_page = {
        "@type": "FAQPage",
        "@id": f"{facts_url}#faq",
        "mainEntity": [
            {
                "@type": "Question",
                "name": item["q"],
                "acceptedAnswer": {"@type": "Answer", "text": item["a"]},
            }
            for item in t["faq"]["items"]
        ],
    }

    return _json_ld_script([website, webpage, person, business, faq_page])


def build_json_ld_case_study(t, cs, current_path):
    lang_code = _lang_of(current_path)
    page_url = url_for(current_path)
    home_url = url_for(lang_home_path(lang_code))

    breadcrumb = {
        "@type": "BreadcrumbList",
        "@id": f"{page_url}#breadcrumb",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": home_url},
            {"@type": "ListItem", "position": 2, "name": t["work"]["heading"], "item": f"{home_url}#work"},
            {"@type": "ListItem", "position": 3, "name": cs["title"], "item": page_url},
        ],
    }

    work = {
        "@type": "CreativeWork",
        "@id": f"{page_url}#creativework",
        "name": cs["title"],
        "headline": cs["one_liner"],
        "description": cs["summary"],
        "url": page_url,
        "author": {"@id": f"{SITE_URL}/#person"},
        "about": cs["tag"],
        "inLanguage": lang_code,
        "datePublished": CASE_STUDIES_DATE_PUBLISHED,
    }
    if cs.get("cover"):
        work["image"] = f"{SITE_URL}/assets/img/{cs['cover']}"

    webpage = {
        "@type": "WebPage",
        "@id": f"{page_url}#webpage",
        "url": page_url,
        "name": cs["title"],
        "description": cs["summary"],
        "inLanguage": lang_code,
        "isPartOf": {"@id": f"{SITE_URL}/#website"},
        "mainEntity": {"@id": f"{page_url}#creativework"},
        "breadcrumb": {"@id": f"{page_url}#breadcrumb"},
    }

    return _json_ld_script([breadcrumb, webpage, work])


def head(t, lang_code, title, description, current_path, alt_paths, article_date=None, markdown_path=None):
    canonical = url_for(current_path)

    hreflang_links = "\n  ".join(
        f'<link rel="alternate" hreflang="{code}" href="{url_for(path)}" />'
        for code, path in alt_paths.items()
    )
    x_default = alt_paths.get("en")
    x_default_link = (
        f'<link rel="alternate" hreflang="x-default" href="{url_for(x_default)}" />'
        if x_default
        else ""
    )
    markdown_link = (
        f'<link rel="alternate" type="text/markdown" href="{href_to(current_path, markdown_path)}" />'
        if markdown_path
        else ""
    )

    og_type = "article" if article_date else "website"
    article_meta = f'\n  <meta property="article:published_time" content="{article_date}" />' if article_date else ""

    return f"""<meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title}</title>
  <meta name="description" content="{description}" />
  <meta name="author" content="Imen Bouzouita" />
  <meta name="robots" content="index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1" />
  <link rel="canonical" href="{canonical}" />
  {hreflang_links}
  {x_default_link}
  {markdown_link}
  <meta property="og:type" content="{og_type}" />
  <meta property="og:title" content="{title}" />
  <meta property="og:description" content="{description}" />
  <meta property="og:url" content="{canonical}" />
  <meta property="og:locale" content="{OG_LOCALE[lang_code]}" />
  <meta property="og:image" content="{SITE_URL}/assets/img/og-cover.jpg" />
  <meta property="og:image:width" content="{OG_COVER_W}" />
  <meta property="og:image:height" content="{OG_COVER_H}" />{article_meta}
  <meta name="twitter:card" content="summary_large_image" />
  <link rel="icon" href="{asset_href(current_path, 'img/favicon.svg')}" type="image/svg+xml" />
  <link rel="apple-touch-icon" href="{asset_href(current_path, 'img/apple-touch-icon.png')}" />
  <link rel="manifest" href="{href_to(current_path, 'manifest.json')}" />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link id="fonts-link" rel="stylesheet" href="{FONTS_URL}" media="print" />
  <noscript><link rel="stylesheet" href="{FONTS_URL}" /></noscript>
  <style>{inline_css(current_path)}</style>
  <meta name="theme-color" content="#0E1B1F" />"""


def lang_switcher_html(current_path, alt_paths):
    items = ""
    for lang in LANGUAGES:
        code = lang["code"]
        if code not in alt_paths:
            continue
        is_current = alt_paths[code] == current_path
        cls = "lang-switch-current" if is_current else ""
        if is_current:
            items += f'<span class="{cls}" aria-current="true">{lang["label"]}</span>'
        else:
            items += f'<a href="{href_to(current_path, alt_paths[code])}" class="{cls}">{lang["label"]}</a>'
    return f'<div class="lang-switch">{items}</div>'


def header_html(t, current_path, alt_paths):
    home = href_to(current_path, lang_home_path(_lang_of(current_path)))
    links = "\n      ".join(
        f'<li><a href="{href}">{label}</a></li>' for label, href in _nav_entries(t, current_path)
    )
    return f"""<header class="site-header">
    <div class="container">
      <a href="{home}" class="logo" aria-label="{t['meta']['logo_aria_label']}">Imen<span class="dot">.</span></a>
      <nav>
        <ul class="nav-links">
          {links}
          <li class="nav-cta"><a href="{CALENDLY}" class="btn btn-primary" target="_blank" rel="noopener">{t['nav']['book_call']}</a></li>
          <li>{lang_switcher_html(current_path, alt_paths)}</li>
        </ul>
      </nav>
      <button class="nav-toggle" aria-label="Toggle menu" aria-expanded="false"><span></span></button>
    </div>
  </header>"""


def footer_html(t, current_path):
    lang_code = _lang_of(current_path)
    home = href_to(current_path, lang_home_path(lang_code))
    terms = href_to(current_path, lang_legal_path(lang_code, "terms"))
    privacy = href_to(current_path, lang_legal_path(lang_code, "privacy"))
    impressum = href_to(current_path, lang_legal_path(lang_code, "impressum"))
    facts = href_to(current_path, lang_facts_path(lang_code))
    return f"""<footer class="site-footer">
    <div class="container">
      <div class="footer-top">
        <div>
          <a href="{home}" class="logo" aria-label="{t['meta']['logo_aria_label']}">Imen<span class="dot">.</span></a>
        </div>
        <nav class="footer-nav">
          <a href="{home}#work-do">{t['nav']['what_i_do']}</a>
          <a href="{home}#work">{t['nav']['case_studies']}</a>
          <a href="{href_to(current_path, lang_resources_index_path(lang_code))}">{t['nav']['resources']}</a>
          <a href="{home}#about">{t['nav']['about']}</a>
          <a href="{home}#faq">{t['nav']['faq']}</a>
          <a href="{home}#contact">{t['nav']['contact']}</a>
        </nav>
        <div class="footer-social">
          <a href="{INSTAGRAM_URL}" target="_blank" rel="noopener" aria-label="Instagram">IG</a>
          <a href="{LINKEDIN_URL}" target="_blank" rel="noopener" aria-label="LinkedIn">in</a>
        </div>
      </div>
      <div class="footer-bottom">
        <span>&copy; 2026 Imen Bouzouita. {t['footer']['rights']}</span>
        <div class="legal-links">
          <a href="{terms}">{t['footer']['terms']}</a>
          <a href="{privacy}">{t['footer']['privacy']}</a>
          <a href="{impressum}">{t['footer']['impressum']}</a>
          <a href="{facts}">{t['grounding']['footer_label']}</a>
          <button type="button" class="link-button" data-cookie-settings>{t['cookie_banner']['settings_link']}</button>
        </div>
      </div>
    </div>
  </footer>"""


def _lang_of(current_path):
    return "de" if current_path.startswith("de/") else "en"


def page_shell(t, title, description, body, current_path, alt_paths, extra_head="", article_date=None, markdown_path=None):
    lang_code = _lang_of(current_path)
    privacy_href = href_to(current_path, lang_legal_path(lang_code, "privacy"))
    cb = t["cookie_banner"]
    cookie_banner_html = f"""<div id="cookie-banner" class="cookie-banner" role="dialog" aria-live="polite" aria-label="Cookie consent" hidden>
    <button type="button" class="cookie-banner-close" data-cookie-close aria-label="{cb['close']}">&times;</button>
    <div class="cookie-banner-inner">
      <p>{cb['text']} <a href="{privacy_href}">{t['footer']['privacy']}</a></p>
      <div class="cookie-banner-actions">
        <button type="button" class="btn btn-ghost" data-cookie-decline>{cb['decline']}</button>
        <button type="button" class="btn btn-primary" data-cookie-accept>{cb['accept']}</button>
      </div>
      <button type="button" class="cookie-manage-toggle" data-cookie-manage aria-expanded="false">
        {cb['manage_label']} <span class="chevron">&#9662;</span>
      </button>
      <div class="cookie-manage-panel" hidden>
        <p class="cookie-purposes-label">{cb['purposes_label']}</p>
        <div class="cookie-purpose">
          <div class="cookie-purpose-head">
            <div>
              <h3>{cb['analytics_label']}</h3>
              <p class="cookie-legal-basis">{cb['analytics_legal_basis']}</p>
            </div>
            <label class="cookie-toggle">
              <input type="checkbox" data-cookie-toggle-analytics />
              <span class="cookie-toggle-track"></span>
            </label>
          </div>
          <p class="cookie-purpose-desc">{cb['analytics_desc']}</p>
        </div>
        <div class="cookie-purpose">
          <div class="cookie-purpose-head">
            <div>
              <h3>{cb['essential_label']}</h3>
              <p class="cookie-legal-basis">{cb['essential_legal_basis']}</p>
            </div>
            <label class="cookie-toggle cookie-toggle--disabled">
              <input type="checkbox" checked disabled />
              <span class="cookie-toggle-track"></span>
            </label>
          </div>
          <p class="cookie-purpose-desc">{cb['essential_desc']}</p>
        </div>
        <button type="button" class="btn btn-primary" data-cookie-confirm>{cb['confirm']}</button>
      </div>
    </div>
  </div>"""
    return f"""<!doctype html>
<html lang="{lang_code}">
<head>
  {head(t, lang_code, title, description, current_path, alt_paths, article_date=article_date, markdown_path=markdown_path)}
  {extra_head}
</head>
<body data-ga4-id="{GA4_MEASUREMENT_ID}" data-contentsquare-src="{CONTENTSQUARE_SRC}">
  {header_html(t, current_path, alt_paths)}
  {body}
  {footer_html(t, current_path)}
  {cookie_banner_html}
  <script src="{asset_href(current_path, 'js/main.js')}?v={MAIN_JS_VERSION}" defer></script>
  <script type="module" src="https://static.cloudflareinsights.com/beacon.min.js" data-cf-beacon='{{"token": "{CLOUDFLARE_ANALYTICS_TOKEN}"}}'></script>
</body>
</html>
"""


def build_index(t, lang_code, alt_paths):
    current_path = lang_home_path(lang_code)

    def _trust_logo_html(logo, lazy, high_priority=False):
        src = asset_href(current_path, "img/logos/" + logo["file"])
        size_class = f" trust-logo--{logo['size']}" if logo.get("size") else ""
        loading = "lazy" if lazy else "eager"
        fetchpriority = ' fetchpriority="high"' if high_priority else ""
        return (
            f'<img class="trust-logo{size_class}" src="{src}" alt="{logo["name"]}" '
            f'width="{logo["w"]}" height="{logo["h"]}" loading="{loading}"{fetchpriority} />'
        )

    # The first pass sits directly below the hero and is visible on first
    # paint at most viewport sizes, so it loads eagerly, and the very first
    # image in DOM order (what Lighthouse's LCP-image check looks at) also
    # gets fetchpriority="high". The duplicate pass exists only for the
    # seamless infinite-scroll loop and is genuinely off-screen until the
    # animation has scrolled through the first pass, so it's safe (and
    # preferable) to keep that one lazy and default-priority.
    trust_track = " ".join(
        _trust_logo_html(logo, lazy=False, high_priority=(i == 0))
        for i, logo in enumerate(TRUST_LOGOS)
    )
    trust_track_lazy = " ".join(_trust_logo_html(logo, lazy=True) for logo in TRUST_LOGOS)
    trust_track_full = trust_track + " " + trust_track_lazy  # duplicate for seamless marquee

    capability_cards = ""
    for i, cap in enumerate(t["capabilities"]["items"], start=1):
        detail_items = "\n            ".join(f"<li>{d}</li>" for d in cap["details"])
        capability_cards += f"""
        <div class="capability-card" data-reveal>
          <span class="capability-index">0{i}</span>
          <h3>{cap['title']}</h3>
          <p>{cap['pitch']}</p>
          <details class="capability-detail">
            <summary>{t['capabilities']['details_label']}</summary>
            <ul>
            {detail_items}
            </ul>
          </details>
        </div>"""

    work_cards = ""
    for cs in t["case_studies"]:
        cs_path = lang_case_study_path(lang_code, cs["slug"])
        card_image = cs.get("card_cover") or cs.get("cover")
        if card_image:
            w, h = image_size(card_image)
            src = asset_href(current_path, "img/" + card_image)
            # A "-480w" sibling, where one exists on disk, is a lighter
            # variant for the single-column mobile layout — the 3-column
            # desktop grid's per-card width is close enough to what mobile
            # needs (~366px at the widest desktop breakpoint) that the
            # full-size file alone is already reasonably right-sized for
            # desktop; only mobile visitors need the smaller one.
            mobile_variant = card_image.replace("card-cover.webp", "card-cover-480w.webp")
            has_mobile_variant = mobile_variant != card_image and os.path.exists(
                os.path.join(ROOT, "assets", "img", mobile_variant)
            )
            if has_mobile_variant:
                mobile_src = asset_href(current_path, "img/" + mobile_variant)
                srcset = f'srcset="{mobile_src} 480w, {src} {w}w" sizes="(max-width: 640px) 100vw, 33vw" '
            else:
                srcset = ""
            cover_html = f'<img class="cover" src="{src}" {srcset}alt="{cs["title"]}" width="{w}" height="{h}" loading="lazy" />'
        else:
            cover_html = '<div class="cover" style="background: linear-gradient(140deg, var(--moonstone), var(--lilac)); position:absolute; inset:0; height:112%;"></div>'
        work_cards += f"""
        <a class="work-card" href="{href_to(current_path, cs_path)}" data-reveal>
          {cover_html}
          <div class="work-card-body">
            <span class="work-tag">{cs['tag']}</span>
            <h3>{cs['title']}</h3>
            <p class="one-liner">{cs['one_liner']}</p>
            <span class="view-prompt">{t['work']['view_project']} &rarr;</span>
          </div>
        </a>"""

    about = t["about"]
    about_paragraphs = "\n          ".join(f"<p>{p}</p>" for p in about["paragraphs"])

    faq_items = ""
    for item in t["faq"]["items"]:
        faq_items += f"""
        <details class="faq-item" data-reveal>
          <summary>{item['q']}</summary>
          <p>{item['a']}</p>
        </details>"""

    contact = t["contact"]
    form = contact["form"]

    body = f"""
  <main>
    <section class="hero">
      <div class="hero-blob b1" data-parallax="0.08"></div>
      <div class="hero-blob b2" data-parallax="0.15"></div>
      <div class="container hero-inner">
        <p class="eyebrow hero-eyebrow">{t['hero']['eyebrow']}</p>
        <h1>{t['hero']['headline_pre']}<em>{t['hero']['headline_em']}</em>{t['hero'].get('headline_post', '')}</h1>
        <p class="lede">{t['hero']['subhead']}</p>
        <div class="hero-ctas">
          <a href="{CALENDLY}" class="btn btn-primary" target="_blank" rel="noopener">{t['hero']['cta_primary']}</a>
          <a href="#work" class="btn-line">{t['hero']['cta_secondary']} &darr;</a>
        </div>
      </div>
      <div class="hero-scroll-hint">{t['hero']['scroll_hint']}<span>&darr;</span></div>
    </section>

    <section class="trust-strip">
      <div class="container">
        <p class="label">{t['hero']['trust_label']}</p>
      </div>
      <div class="marquee"><div class="marquee-track">{trust_track_full}</div></div>
    </section>

    <section id="approach">
      <div class="container approach-grid">
        <div data-reveal>
          <p class="eyebrow">{t['approach']['eyebrow']}</p>
          <h2>{t['approach']['heading']}</h2>
          <p class="lede">{t['approach']['body']}</p>
        </div>
        <div class="approach-practice" data-reveal>
          <p class="approach-practice-label">{t['approach']['practice_heading']}</p>
          <ul class="approach-list">
            {"".join(f"<li>{item}</li>" for item in t['approach']['items'])}
          </ul>
        </div>
      </div>
    </section>

    <section id="work-do">
      <div class="container">
        <div class="section-head" data-reveal>
          <p class="eyebrow">{t['capabilities']['eyebrow']}</p>
          <h2>{t['capabilities']['heading']}</h2>
        </div>
        <div class="capabilities-grid">{capability_cards}
        </div>
      </div>
    </section>

    <section id="work">
      <div class="container">
        <div class="section-head" data-reveal>
          <p class="eyebrow">{t['work']['eyebrow']}</p>
          <h2>{t['work']['heading']}</h2>
        </div>
        <div class="work-grid">{work_cards}
        </div>
      </div>
    </section>

    <section id="about" class="about-section">
      <div class="container about-grid">
        <div class="about-portrait-wrap" data-reveal>
          <div class="about-portrait-frame"></div>
          <picture>
            <source srcset="{asset_href(current_path, 'img/imen-portrait.webp')}" type="image/webp" />
            <img class="about-portrait" src="{asset_href(current_path, 'img/imen-portrait.jpg')}" alt="Portrait of Imen Bouzouita" loading="lazy" width="840" height="1120" />
          </picture>
        </div>
        <div class="about-text" data-reveal>
          <p class="eyebrow">{about['eyebrow']}</p>
          <h2 class="on-dark" style="margin-block: 1rem 1.5rem;">{about['heading']}</h2>
          {about_paragraphs}
          <img class="signature" src="{asset_href(current_path, 'img/logos/logo.png')}" alt="Imen Bouzouita signature" width="724" height="208" loading="lazy" />
        </div>
      </div>
    </section>

    <section id="faq">
      <div class="container">
        <div class="section-head" data-reveal>
          <p class="eyebrow">{t['faq']['eyebrow']}</p>
          <h2>{t['faq']['heading']}</h2>
        </div>
        <div class="faq-list">{faq_items}
        </div>
      </div>
    </section>

    <section id="contact">
      <div class="contact-section" data-reveal>
        <div class="container contact-inner">
          <div class="contact-grid">
            <div>
              <h2>{contact['heading']}</h2>
              <p class="lede">{contact['body']}</p>
              <div class="hero-ctas mt-lg">
                <a href="{CALENDLY}" class="btn btn-primary" target="_blank" rel="noopener">{contact['cta']}</a>
              </div>
            </div>
            <div>
              <form id="contact-form" action="{FORMSPREE_ACTION}" method="POST"
                data-msg-not-wired="{form['msg_not_wired']}"
                data-msg-sending="{form['sending']}"
                data-msg-success="{form['msg_success']}"
                data-msg-error="{form['msg_error']}"
                data-msg-network="{form['msg_network']}">
                <input type="text" name="_gotcha" style="display:none" tabindex="-1" autocomplete="off" />
                <input type="text" name="company" class="hp-decoy" style="display:none" tabindex="-1" autocomplete="off" />
                <div class="form-field">
                  <label for="name">{form['name_label']}</label>
                  <input type="text" id="name" name="name" required />
                </div>
                <div class="form-field">
                  <label for="email">{form['email_label']}</label>
                  <input type="email" id="email" name="email" required />
                </div>
                <div class="form-field">
                  <label for="message">{form['message_label']}</label>
                  <textarea id="message" name="message" rows="4" required></textarea>
                </div>
                <button type="submit" class="btn btn-primary" style="width:100%; justify-content:center;">{form['submit']}</button>
                <p class="form-status" role="status"></p>
              </form>
            </div>
          </div>
        </div>
      </div>
    </section>
  </main>
"""
    # llms.txt is already a clean Markdown summary of the homepage's content
    # (English-only, by its own design), so the homepage just points its
    # discovery link at that instead of generating a redundant sibling file.
    markdown_path = "llms.txt" if lang_code == "en" else None
    html = page_shell(t, t["meta"]["site_title"], t["meta"]["site_description"], body, current_path, alt_paths, extra_head=build_json_ld_home(t, current_path), markdown_path=markdown_path)
    write(current_path, html)


def _md_sibling_path(html_path):
    assert html_path.endswith("index.html")
    return html_path[: -len("index.html")] + "index.md"


def build_markdown_case_study(t, cs):
    """Clean Markdown mirror of a case study — discoverable via the page's
    <link rel="alternate" type="text/markdown">, for agents that would
    otherwise have to parse the full HTML/CSS/JSON-LD to get the content."""
    lines = [f"# {cs['title']}", "", cs["one_liner"], "", cs["summary"], ""]
    if cs.get("highlight"):
        lines += [f"> {cs['highlight']}", ""]
    for label, value in cs["meta"]:
        lines.append(f"- **{label}:** {value}")
    lines.append("")
    for heading, content in cs["sections"]:
        lines.append(f"## {heading}")
        lines.append("")
        for p in _as_list(content):
            lines.append(_inline_to_markdown(p))
            lines.append("")
    return "\n".join(lines)


def build_markdown_resource_article(t, article):
    lines = [f"# {article['title']}", "", article["excerpt"], ""]
    for section in article["sections"]:
        if section.get("heading"):
            lines.append(f"## {section['heading']}")
            lines.append("")
        for p in _as_list(section.get("body")):
            lines.append(_inline_to_markdown(p))
            lines.append("")
        for item in section.get("items", []):
            lines.append(f"### {item['heading']}")
            lines.append("")
            for p in _as_list(item.get("body")):
                lines.append(_inline_to_markdown(p))
                lines.append("")
    return "\n".join(lines)


def build_markdown_facts(t):
    g = t["grounding"]
    lbl = g["labels"]
    who_for = t["faq"]["items"][6]["a"]
    lines = [
        f"# {g['heading']}", "", g["human_note"], "",
        f"{lbl['page_created']}: {g['page_created']} · {lbl['last_updated']}: {g['last_updated']}", "",
        f"## {g['entity_summary_heading']}", "",
    ]
    lines += [
        f"- **{lbl['entity']}:** Imen Bouzouita",
        f"- **{lbl['entity_class']}:** {g['entity_class']}",
        f"- **{lbl['legal_form']}:** {g['legal_form']}",
        f"- **{lbl['headquarters']}:** {g['headquarters_value']}",
        f"- **{lbl['service_location']}:** {g['service_location_value']}",
        f"- **{lbl['industry']}:** {g['industry_value']}",
        f"- **{lbl['branches']}:** {g['branches_value']}",
        f"- **{lbl['services']}:** " + ", ".join(cap["title"] for cap in t["capabilities"]["items"]),
        f"- **{lbl['experience']}:** {g['experience_value']}",
        f"- **{lbl['known_for']}:** {g['known_for']}",
        "",
        f"## {g['core_facts_heading']}", "",
        t["about"]["paragraphs"][0], "",
        g["background_text"], "",
        f"## {g['identifiers_heading']}", "",
        f"- **{lbl['website']}:** {SITE_URL}",
        f"- **{lbl['linkedin']}:** {LINKEDIN_URL}",
        f"- **{lbl['instagram']}:** {INSTAGRAM_URL}",
        f"- **{lbl['vat_id']}:** {BUSINESS_VAT_ID}",
        f"- **{lbl['languages']}:** {g['languages_value']}",
        "",
        f"## {g['services_heading']}", "",
    ]
    for cap in t["capabilities"]["items"]:
        lines.append(f"- **{cap['title']}.** {cap['pitch']}")
    lines += ["", f"## {g['who_for_heading']}", "", who_for, "", f"## {g['clients_heading']}", ""]
    lines.append(f"{t['hero']['trust_label']} {', '.join(logo['name'] for logo in TRUST_LOGOS)}.")
    lines.append("")
    for cs in t["case_studies"]:
        lines.append(f"- **{cs['title']}.** {cs['one_liner']}")
    lines += ["", f"## {g['faq_heading']}", ""]
    for item in t["faq"]["items"]:
        lines.append(f"**{item['q']}**")
        lines.append("")
        lines.append(item["a"])
        lines.append("")
    return "\n".join(lines)


def build_case_study(t, lang_code, cs, prev_cs, next_cs, alt_paths):
    current_path = lang_case_study_path(lang_code, cs["slug"])

    sections_html = ""
    for heading, content in cs["sections"]:
        paragraphs = content if isinstance(content, list) else [content]
        paras_html = "\n        ".join(f"<p>{p}</p>" for p in paragraphs)
        sections_html += f"<h2>{heading}</h2>\n        {paras_html}\n        "

    meta_html = "\n          ".join(
        f"<div><dt>{label}</dt><dd>{value}</dd></div>" for label, value in cs["meta"]
    )

    highlight_html = ""
    if cs.get("highlight"):
        highlight_html = f'<p class="case-highlight">{cs["highlight"]}</p>'

    live_url_html = ""
    if cs.get("live_url"):
        live_url_html = f'<a href="{cs["live_url"]}" class="btn btn-ghost case-live-link" target="_blank" rel="noopener">{t["meta"]["visit_live_site_label"]} &nearr;</a>'

    if cs.get("cover"):
        cover_src = asset_href(current_path, "img/" + cs["cover"])
        cover_w, cover_h = image_size(cs["cover"])
        cover_html = (
            f'<img src="{cover_src}" alt="{cs["title"]}" width="{cover_w}" height="{cover_h}" '
            f'loading="eager" fetchpriority="high" />'
        )
    else:
        cover_html = '<div style="width:100%; height:100%; display:flex; align-items:center; justify-content:center; color:rgba(14,27,31,0.35); font-family:var(--font-display);">Cover image placeholder</div>'

    gallery_html = ""
    if cs.get("gallery"):
        is_pair = len(cs["gallery"]) == 2

        def _gallery_img(entry):
            src, wide = entry if isinstance(entry, list) else (entry, False)
            # In a 2-image gallery, a spanning "wide" image can't fit beside
            # the other one (only 2 columns total), so they'd stack instead
            # of sitting side by side — force single-column sizing for pairs
            # so both always land in the same row.
            cls = ' class="wide"' if wide and not is_pair else ""
            w, h = image_size(src)
            return (
                f'<img{cls} src="{asset_href(current_path, "img/" + src)}" alt="{cs["title"]}" '
                f'width="{w}" height="{h}" loading="lazy" />'
            )

        gallery_items = "\n          ".join(_gallery_img(g) for g in cs["gallery"])
        gallery_cls = "case-gallery"
        if cs.get("gallery_large"):
            gallery_cls += " case-gallery--lg"
        if is_pair:
            gallery_cls += " case-gallery--pair"
        gallery_html = f"""
        <div class="{gallery_cls}" data-reveal>
          {gallery_items}
        </div>"""

    prev_href = href_to(current_path, lang_case_study_path(lang_code, prev_cs["slug"]))
    next_href = href_to(current_path, lang_case_study_path(lang_code, next_cs["slug"]))
    home_href = href_to(current_path, lang_home_path(lang_code))

    body = f"""
  <main>
    <section class="page-hero">
      <div class="container">
        <div class="tag-row"><span class="work-tag" style="position:static;">{cs['tag']}</span></div>
        <p class="eyebrow">{t['meta']['case_study_label']}</p>
        <h1>{cs['title']}</h1>
        <p class="lede">{cs['one_liner']}</p>
        {live_url_html}
        <div class="case-cover" data-reveal>
          {cover_html}
        </div>
        <dl class="case-meta" data-reveal>
          {meta_html}
        </dl>
        <div class="case-body" data-reveal>
          <p class="lede" style="color: var(--ink);">{cs['summary']}</p>
          {highlight_html}
          {sections_html}
        </div>
        {gallery_html}
        <div class="case-nav">
          <a href="{prev_href}" class="btn-line">&larr; {prev_cs['title']}</a>
          <a href="{home_href}#work" class="btn btn-ghost">{t['work']['all_work']}</a>
          <a href="{next_href}" class="btn-line">{next_cs['title']} &rarr;</a>
        </div>
      </div>
    </section>
  </main>
"""
    md_path = _md_sibling_path(current_path)
    write(md_path, build_markdown_case_study(t, cs))

    title = f"{cs['title']} — {t['meta']['case_study_label']} — Imen Bouzouita"
    description = meta_description(cs["one_liner"], cs["summary"])
    html = page_shell(t, title, description, body, current_path, alt_paths, extra_head=build_json_ld_case_study(t, cs, current_path), article_date=CASE_STUDIES_DATE_PUBLISHED, markdown_path=md_path)
    write(current_path, html)


def build_resources_index(t, lang_code, alt_paths):
    current_path = lang_resources_index_path(lang_code)
    res = t["resources"]

    def _render_card(article):
        article_path = lang_resource_path(lang_code, article["slug"])
        read_time = res["read_time_label"].format(n=estimate_read_minutes(article))
        category_html = (
            f'<span class="resource-category">{article["category"]}</span>' if article.get("category") else ""
        )
        return f"""
        <a class="resource-card" href="{href_to(current_path, article_path)}" data-reveal>
          <div class="resource-card-meta">
            {category_html}
          </div>
          <h3>{article['title']}</h3>
          <p>{article['excerpt']}</p>
          <span class="resource-read-more">{res['read_more']} &middot; {read_time} &rarr;</span>
        </a>"""

    if res["items"]:
        # Grouped by cluster, in the fixed editorial order defined in
        # content — not every cluster has articles yet, so empty ones are
        # skipped rather than shown as bare headings with nothing under them.
        clusters_html = ""
        sidenav_links = ""
        clustered_slugs = set()
        for cluster in res["clusters"]:
            cluster_articles = [a for a in res["items"] if a.get("cluster") == cluster["key"]]
            if not cluster_articles:
                continue
            clustered_slugs.update(a["slug"] for a in cluster_articles)
            cards = "".join(_render_card(a) for a in cluster_articles)
            clusters_html += f"""
          <div class="resource-cluster" id="{cluster['key']}">
            <h2 class="resource-cluster-heading">{cluster['name']}</h2>
            <div class="resource-list">{cards}
            </div>
          </div>"""
            sidenav_links += f'\n          <a href="#{cluster["key"]}">{cluster["name"]}</a>'
        # An article with a missing/mistyped cluster key would otherwise
        # silently vanish from the index while its own page still builds
        # and stays reachable — surface it instead of hiding it.
        stray = [a for a in res["items"] if a["slug"] not in clustered_slugs]
        if stray:
            cards = "".join(_render_card(a) for a in stray)
            clusters_html += f'\n          <div class="resource-cluster"><div class="resource-list">{cards}\n            </div></div>'

        list_html = f"""<div class="resources-layout">
          <nav class="resources-sidenav" aria-label="{res['topics_label']}">
            <p class="resources-sidenav-label">{res['topics_label']}</p>{sidenav_links}
          </nav>
          <div class="resources-content">{clusters_html}
          </div>
        </div>"""
    else:
        list_html = f'<p class="resource-empty">{res["empty_state"]}</p>'

    body = f"""
  <main>
    <section class="page-hero resources-hero">
      <div class="container">
        <p class="eyebrow">{res['eyebrow']}</p>
        <h1>{res['heading']}</h1>
        <p class="lede">{res['intro']}</p>
        <div class="mt-lg">{list_html}</div>
      </div>
    </section>
  </main>
"""
    title = f"{res['heading']} — Imen Bouzouita"
    html = page_shell(t, title, res["intro"], body, current_path, alt_paths, extra_head=build_json_ld_resources_index(t, current_path))
    write(current_path, html)


def build_resource_article(t, lang_code, article, alt_paths):
    current_path = lang_resource_path(lang_code, article["slug"])
    res = t["resources"]

    sections_html = ""
    for section in article["sections"]:
        heading_html = f"<h2>{section['heading']}</h2>\n        " if section.get("heading") else ""
        body_html = "\n        ".join(f"<p>{p}</p>" for p in _as_list(section.get("body")))
        items_html = ""
        for item in section.get("items", []):
            item_body = "\n          ".join(f"<p>{p}</p>" for p in _as_list(item.get("body")))
            items_html += f"<h3>{item['heading']}</h3>\n          {item_body}\n        "
        sections_html += f"{heading_html}{body_html}{items_html}\n        "

    read_time = res["read_time_label"].format(n=estimate_read_minutes(article))
    category_html = (
        f'<span class="resource-category">{article["category"]}</span>' if article.get("category") else ""
    )

    cover_html = ""
    if article.get("cover"):
        cover_src = asset_href(current_path, "img/" + article["cover"])
        cover_w, cover_h = image_size(article["cover"])
        cover_html = (
            f'<div class="case-cover" data-reveal><img src="{cover_src}" alt="{article["title"]}" '
            f'width="{cover_w}" height="{cover_h}" loading="eager" fetchpriority="high" /></div>'
        )

    resources_href = href_to(current_path, lang_resources_index_path(lang_code))

    body = f"""
  <main>
    <section class="page-hero resources-hero">
      <div class="container">
        <div class="tag-row">{category_html}<span class="resource-date">{read_time}</span></div>
        <h1>{article['title']}</h1>
        {cover_html}
        <div class="case-body" data-reveal>
          <p class="lede">{article['excerpt']}</p>
          {sections_html}
        </div>
        <div class="case-nav" style="justify-content:flex-start;">
          <a href="{resources_href}" class="btn btn-ghost">&larr; {res['all_resources']}</a>
        </div>
      </div>
    </section>
  </main>
"""
    md_path = _md_sibling_path(current_path)
    write(md_path, build_markdown_resource_article(t, article))

    title = f"{article['title']} — {res['eyebrow']} — Imen Bouzouita"
    html = page_shell(t, title, article["excerpt"], body, current_path, alt_paths, extra_head=build_json_ld_resource_article(t, article, current_path), article_date=article["date"], markdown_path=md_path)
    write(current_path, html)


def build_facts_page(t, lang_code, alt_paths):
    current_path = lang_facts_path(lang_code)
    g = t["grounding"]
    lbl = g["labels"]
    who_for = t["faq"]["items"][6]["a"]

    def _row(label, value):
        return f"<div class=\"facts-row\"><dt>{label}</dt><dd>{value}</dd></div>"

    services_summary = ", ".join(cap["title"] for cap in t["capabilities"]["items"])

    entity_summary = "".join([
        _row(lbl["entity"], "Imen Bouzouita"),
        _row(lbl["entity_class"], g["entity_class"]),
        _row(lbl["legal_form"], g["legal_form"]),
        _row(lbl["headquarters"], g["headquarters_value"]),
        _row(lbl["service_location"], g["service_location_value"]),
        _row(lbl["industry"], g["industry_value"]),
        _row(lbl["branches"], g["branches_value"]),
        _row(lbl["services"], services_summary),
        _row(lbl["experience"], g["experience_value"]),
        _row(lbl["known_for"], g["known_for"]),
    ])

    identifiers = "".join([
        _row(lbl["website"], f'<a href="{SITE_URL}">{SITE_URL.replace("https://", "")}</a>'),
        _row(lbl["linkedin"], f'<a href="{LINKEDIN_URL}" target="_blank" rel="noopener">{LINKEDIN_URL}</a>'),
        _row(lbl["instagram"], f'<a href="{INSTAGRAM_URL}" target="_blank" rel="noopener">{INSTAGRAM_URL}</a>'),
        _row(lbl["vat_id"], BUSINESS_VAT_ID),
        _row(lbl["languages"], g["languages_value"]),
    ])

    services_html = "".join(
        f"<li><strong>{cap['title']}.</strong> {cap['pitch']}</li>"
        for cap in t["capabilities"]["items"]
    )

    case_studies_html = "".join(
        f"<li><strong>{cs['title']}.</strong> {cs['one_liner']}</li>"
        for cs in t["case_studies"]
    )

    home_href = href_to(current_path, lang_home_path(lang_code))

    body = f"""
  <main>
    <section class="page-hero">
      <div class="container">
        <p class="eyebrow">{g['eyebrow']}</p>
        <h1>{g['heading']}</h1>
        <p class="lede">{g['human_note']}</p>
        <p class="facts-meta-line">{lbl['page_created']}: {g['page_created']} &middot; {lbl['last_updated']}: {g['last_updated']}</p>

        <div class="legal-content mt-lg">
          <h2>{g['entity_summary_heading']}</h2>
          <dl class="facts-table">{entity_summary}</dl>

          <h2>{g['core_facts_heading']}</h2>
          <p>{t['about']['paragraphs'][0]}</p>
          <p>{g['background_text']}</p>

          <h2>{g['identifiers_heading']}</h2>
          <dl class="facts-table">{identifiers}</dl>

          <h2>{g['services_heading']}</h2>
          <ul>{services_html}</ul>

          <h2>{g['who_for_heading']}</h2>
          <p>{who_for}</p>

          <h2>{g['clients_heading']}</h2>
          <p>{t['hero']['trust_label']} {', '.join(logo['name'] for logo in TRUST_LOGOS)}.</p>
          <ul>{case_studies_html}</ul>

          <h2>{g['references_heading']}</h2>
          <ul>
            <li><a href="{home_href}">{g['ref_home']}</a></li>
            <li><a href="{home_href}#work">{g['ref_work']}</a></li>
            <li><a href="{home_href}#about">{g['ref_about']}</a></li>
            <li><a href="{home_href}#contact">{g['ref_contact']}</a></li>
            <li><a href="{LINKEDIN_URL}" target="_blank" rel="noopener">LinkedIn</a></li>
            <li><a href="{INSTAGRAM_URL}" target="_blank" rel="noopener">Instagram</a></li>
          </ul>

          <h2>{g['faq_heading']}</h2>
          <div class="faq-list" style="margin-inline: 0;">
            {"".join(f'<details class="faq-item" data-reveal><summary>{item["q"]}</summary><p>{item["a"]}</p></details>' for item in t["faq"]["items"])}
          </div>
        </div>
      </div>
    </section>
  </main>
"""
    md_path = _md_sibling_path(current_path)
    write(md_path, build_markdown_facts(t))

    title = f"{g['heading']} — Imen Bouzouita"
    html = page_shell(t, title, g["human_note"], body, current_path, alt_paths, extra_head=build_json_ld_facts(t, current_path), markdown_path=md_path)
    write(current_path, html)


LEGAL_META_DESCRIPTIONS = {
    ("en", "terms"): "General Terms and Conditions for UX, CRO, and digital strategy consulting services provided by Imen Bouzouita, covering engagement terms and deliverables.",
    ("en", "privacy"): "How imenbouzouita.com collects, uses, and protects your personal data, including analytics, cookies, and the contact form, and your rights under GDPR.",
    ("en", "impressum"): "Legal notice (Impressum) for Imen Bouzouita, independent UX, CRO & digital strategy consultant based in Berlin, Germany — company and contact details.",
    ("de", "terms"): "Allgemeine Geschäftsbedingungen für UX-, CRO- und Digitalstrategie-Beratungsleistungen von Imen Bouzouita — Vertragsbedingungen, Leistungen und Pflichten.",
    ("de", "privacy"): "Wie imenbouzouita.com personenbezogene Daten erhebt, nutzt und schützt, inklusive Analyse-Tools, Cookies und Kontaktformular, sowie Ihre Rechte nach DSGVO.",
    ("de", "impressum"): "Impressum von Imen Bouzouita, selbstständige UX-, CRO- und Digitalstrategie-Beraterin mit Sitz in Berlin — Angaben gemäß § 5 TMG und Kontaktdaten.",
}


def build_legal(t, lang_code, slug, alt_paths):
    current_path = lang_legal_path(lang_code, slug)
    entry = t["legal"][slug]
    body = f"""
  <main>
    <section class="page-hero">
      <div class="container">
        <p class="eyebrow">{t['meta']['legal_label']}</p>
        <h1>{entry['title']}</h1>
        <div class="legal-content mt-lg">
          {entry['content_html']}
        </div>
      </div>
    </section>
  </main>
"""
    title = f"{entry['title']} — Imen Bouzouita"
    description = LEGAL_META_DESCRIPTIONS[(lang_code, slug)]
    html = page_shell(t, title, description, body, current_path, alt_paths, extra_head=build_json_ld_legal(t, entry, current_path))
    write(current_path, html)


def build_json_ld_legal(t, entry, current_path):
    lang_code = _lang_of(current_path)
    page_url = url_for(current_path)
    webpage = {
        "@type": "WebPage",
        "@id": f"{page_url}#webpage",
        "url": page_url,
        "name": entry["title"],
        "inLanguage": lang_code,
        "isPartOf": {"@id": f"{SITE_URL}/#website"},
        "about": {"@id": f"{SITE_URL}/#business"},
    }
    return _json_ld_script([webpage])


def build_json_ld_resources_index(t, current_path):
    lang_code = _lang_of(current_path)
    page_url = url_for(current_path)
    blog = {
        "@type": "Blog",
        "@id": f"{page_url}#blog",
        "name": t["resources"]["heading"],
        "url": page_url,
        "inLanguage": lang_code,
        "isPartOf": {"@id": f"{SITE_URL}/#website"},
        "publisher": {"@id": f"{SITE_URL}/#business"},
    }
    webpage = {
        "@type": "WebPage",
        "@id": f"{page_url}#webpage",
        "url": page_url,
        "name": t["resources"]["heading"],
        "description": t["resources"]["intro"],
        "inLanguage": lang_code,
        "isPartOf": {"@id": f"{SITE_URL}/#website"},
        "about": {"@id": f"{SITE_URL}/#business"},
    }
    return _json_ld_script([webpage, blog])


def build_json_ld_resource_article(t, article, current_path):
    lang_code = _lang_of(current_path)
    page_url = url_for(current_path)
    home_url = url_for(lang_home_path(lang_code))
    resources_url = url_for(lang_resources_index_path(lang_code))

    breadcrumb = {
        "@type": "BreadcrumbList",
        "@id": f"{page_url}#breadcrumb",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": home_url},
            {"@type": "ListItem", "position": 2, "name": t["resources"]["eyebrow"], "item": resources_url},
            {"@type": "ListItem", "position": 3, "name": article["title"], "item": page_url},
        ],
    }

    post = {
        "@type": "BlogPosting",
        "@id": f"{page_url}#article",
        "headline": article["title"],
        "description": article["excerpt"],
        "url": page_url,
        "author": {"@id": f"{SITE_URL}/#person"},
        "publisher": {"@id": f"{SITE_URL}/#business"},
        "inLanguage": lang_code,
        "datePublished": article["date"],
        "mainEntityOfPage": {"@id": f"{page_url}#webpage"},
    }
    if article.get("cover"):
        post["image"] = f"{SITE_URL}/assets/img/{article['cover']}"

    webpage = {
        "@type": "WebPage",
        "@id": f"{page_url}#webpage",
        "url": page_url,
        "name": article["title"],
        "description": article["excerpt"],
        "inLanguage": lang_code,
        "isPartOf": {"@id": f"{SITE_URL}/#website"},
        "mainEntity": {"@id": f"{page_url}#article"},
        "breadcrumb": {"@id": f"{page_url}#breadcrumb"},
    }

    return _json_ld_script([breadcrumb, webpage, post])


def build_404(t):
    current_path = "404.html"
    nf = t["not_found"]
    body = f"""
  <main>
    <section class="page-hero text-center">
      <div class="container">
        <p class="eyebrow" style="justify-content:center;">{nf['eyebrow']}</p>
        <h1>{nf['heading']}</h1>
        <p class="lede">{nf['lede']}</p>
        <div class="hero-ctas mt-lg" style="justify-content:center;">
          <a href="/" class="btn btn-primary">{nf['cta']}</a>
        </div>
      </div>
    </section>
  </main>
"""
    html = page_shell(t, t["meta"]["not_found_title"], t["meta"]["not_found_description"], body, current_path, {"en": current_path})
    write(current_path, html)


AI_TRAINING_BOTS = [
    "CCBot",
    "Bytespider",
    "Amazonbot",
    "Diffbot",
    "Omgilibot",
    "Timpibot",
    "ImagesiftBot",
    "cohere-ai",
]

# The live-browsing/search-indexing counterparts of the training bots
# above — already permitted by the default "User-agent: *" rule, listed
# explicitly here too for clarity and robustness rather than relying
# solely on the wildcard.
AI_INPUT_BOTS = [
    "OAI-SearchBot",
    "ChatGPT-User",
    "Claude-User",
    "Claude-SearchBot",
    "PerplexityBot",
]

# Training crawlers explicitly allowed (opted back in): OpenAI, Anthropic
# (both its current bot, ClaudeBot, and its older/alternate identifier,
# anthropic-ai), Google, Meta, and Apple's training bots.
AI_TRAINING_BOTS_ALLOWED = [
    "GPTBot",
    "ClaudeBot",
    "anthropic-ai",
    "Google-Extended",
    "Meta-ExternalAgent",
    "Applebot-Extended",
]


_LASTMOD_CACHE = {}


def _lastmod(rel_path):
    """Sitemap <lastmod> for the output file at `rel_path`: the date of the
    last commit that actually changed it. Each generated HTML file is its
    own git blob (even though several share one content/en.json source), so
    this stays accurate per page rather than bumping every page's date on
    any content edit. Falls back to today for a file with no commit yet
    (new page, not committed) or if git isn't available."""
    if rel_path in _LASTMOD_CACHE:
        return _LASTMOD_CACHE[rel_path]

    date = None
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%aI", "--", rel_path],
            cwd=ROOT, capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            date = result.stdout.strip()[:10]
    except (OSError, subprocess.SubprocessError):
        pass

    date = date or datetime.date.today().isoformat()
    _LASTMOD_CACHE[rel_path] = date
    return date


def build_robots_sitemap(content):
    bot_blocks = "\n".join(f"User-agent: {bot}\nDisallow: /\n" for bot in AI_TRAINING_BOTS)
    allow_blocks = "\n".join(f"User-agent: {bot}\nAllow: /\n" for bot in AI_INPUT_BOTS)
    training_allow_blocks = "\n".join(f"User-agent: {bot}\nAllow: /\n" for bot in AI_TRAINING_BOTS_ALLOWED)
    robots_txt = f"""User-agent: *
Allow: /

Content-Signal: search=yes, ai-input=yes, ai-train=yes

# Explicitly allowed: AI assistants browsing or answering a live user's
# question about this site (a separate, permitted use from training —
# see /ai.txt and the Content-Signal line above). Already covered by
# the wildcard rule, listed explicitly for clarity.

{allow_blocks}
# Explicitly allowed: AI training for OpenAI, Anthropic, Google, Meta,
# and Apple.

{training_allow_blocks}
# Other AI-training/data-scraping crawlers are still blocked below.

{bot_blocks}
Sitemap: {SITE_URL}/sitemap.xml
"""
    write("robots.txt", robots_txt)

    write("ai.txt", f"""# ai.txt for {SITE_URL}
#
# AI training is allowed for OpenAI, Anthropic, Google, Meta, and
# Apple. Other AI/data-scraping crawlers are blocked — see /robots.txt
# for the full, per-crawler breakdown.
#
# There is no formal, widely-adopted standard for ai.txt yet. The
# directives that crawlers actually honour live in /robots.txt, which
# blocks known AI-training bots by name and declares the same policy
# below via the Content-Signal convention:
# https://developers.cloudflare.com/bots/additional-configurations/content-signals-policy/

Content-Signal: search=yes, ai-input=yes, ai-train=yes

# search=yes    -- this content may be indexed for search results
# ai-input=yes  -- AI assistants may read this content to answer a
#                  user's question about it (RAG, citation, live browsing)
# ai-train=yes  -- this content may be used to train or fine-tune AI/ML
#                  models — allowed for OpenAI, Anthropic, Google,
#                  Meta, and Apple specifically (see the named Allow
#                  rules in /robots.txt); other AI-training/data-
#                  scraping crawlers are still individually blocked
#                  there.
""")

    all_paths = []
    for lang in LANGUAGES:
        code = lang["code"]
        t = content[code]
        paths = [lang_home_path(code), lang_facts_path(code)] + [
            lang_legal_path(code, slug) for slug in ("terms", "privacy", "impressum")
        ] + [lang_case_study_path(code, cs["slug"]) for cs in t["case_studies"]] + [
            lang_resources_index_path(code)
        ] + [lang_resource_path(code, a["slug"]) for a in t["resources"]["items"]]
        all_paths.extend((code, p) for p in paths)

    # group by "page family" (path with language prefix stripped) so we can
    # emit hreflang alternates between the en/de versions of the same page
    by_family = {}
    for code, p in all_paths:
        d = next(l["dir"] for l in LANGUAGES if l["code"] == code)
        family = p[len(d):] if d and p.startswith(d) else p
        by_family.setdefault(family, {})[code] = p

    entries = []
    for family, variants in by_family.items():
        for code, p in variants.items():
            alt_links = "\n      ".join(
                f'<xhtml:link rel="alternate" hreflang="{alt_code}" href="{url_for(alt_p)}" />'
                for alt_code, alt_p in variants.items()
            )
            entries.append(
                f"  <url>\n    <loc>{url_for(p)}</loc>\n    <lastmod>{_lastmod(p)}</lastmod>\n"
                f"      {alt_links}\n  </url>"
            )

    sitemap = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">
{chr(10).join(entries)}
</urlset>
"""
    write("sitemap.xml", sitemap)


def build_security_txt():
    # Fixed (not computed at build time) so rebuilds don't churn this file
    # on every run — update this date by hand roughly once a year.
    security_txt = f"""Contact: mailto:contact@imenbouzouita.com
Expires: 2027-09-07T00:00:00.000Z
Preferred-Languages: en, de
Canonical: {SITE_URL}/.well-known/security.txt
"""
    write(".well-known/security.txt", security_txt)
    write("security.txt", security_txt)


def build_manifest(content):
    """Minimal web app manifest. This site isn't an installable app, but the
    manifest is what unlocks "Add to Home Screen"/install-prompt eligibility
    in Chromium browsers and gives Android a proper icon/splash screen
    instead of a generic one — worth the few lines even without full PWA
    features (no service worker, offline support, etc.)."""
    t = content["en"]
    manifest = {
        "name": t["meta"]["site_title"],
        "short_name": "Imen Bouzouita",
        "description": t["meta"]["site_description"],
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": "#0E1B1F",
        "theme_color": "#0E1B1F",
        "icons": [
            {"src": "/assets/img/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": "/assets/img/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
            # A dedicated maskable icon, not just the "any" ones relabeled:
            # Android crops adaptive icons into a circle/squircle, so the
            # logomark here is scaled down to sit inside that safe zone —
            # reusing the full-bleed icons above would clip the letter and
            # dot at the edges once masked.
            {"src": "/assets/img/icon-512-maskable.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
    }
    write("manifest.json", json.dumps(manifest, indent=2) + "\n")


def build_llms_txt(content):
    """llms.txt (https://llmstxt.org/) — a plain-markdown site summary aimed
    at LLMs/AI crawlers, generated from the same English content data as the
    rest of the site so it can't drift out of sync with real copy edits."""
    t = content["en"]
    hero = t["hero"]
    about = t["about"]

    lines = [
        f"# {t['meta']['site_title']}",
        "",
        f"> {t['meta']['site_description']}",
        "",
        f"{hero['eyebrow']}. {about['paragraphs'][0]}",
        "",
        "## What I Do",
        "",
    ]
    for cap in t["capabilities"]["items"]:
        lines.append(f"- [{cap['title']}]({url_for(lang_home_path('en'))}#work-do): {cap['pitch']}")

    lines += ["", "## Case Studies", ""]
    for cs in t["case_studies"]:
        cs_url = url_for(lang_case_study_path("en", cs["slug"]))
        lines.append(f"- [{cs['title']}]({cs_url}): {cs['one_liner']} — {cs['summary']}")

    if t["resources"]["items"]:
        lines += ["", "## Resources", ""]
        for article in t["resources"]["items"]:
            article_url = url_for(lang_resource_path("en", article["slug"]))
            lines.append(f"- [{article['title']}]({article_url}): {article['excerpt']}")

    lines += [
        "",
        "## About",
        "",
        f"- [About]({url_for(lang_home_path('en'))}#about): {about['paragraphs'][1]}",
        "",
        "## Contact",
        "",
        f"- [{hero['cta_primary']}]({CALENDLY})",
        f"- [Contact form]({url_for(lang_home_path('en'))}#contact)",
        "",
        "## Optional",
        "",
        f"- [llms-full.txt]({SITE_URL}/llms-full.txt): full content of every page, for agents that won't crawl deeper",
        f"- [Terms]({url_for(lang_legal_path('en', 'terms'))})",
        f"- [Privacy]({url_for(lang_legal_path('en', 'privacy'))})",
        f"- [Impressum]({url_for(lang_legal_path('en', 'impressum'))})",
        f"- [Deutsch]({url_for(lang_home_path('de'))}): German-language version of this site",
        "",
    ]
    write("llms.txt", "\n".join(lines))


def build_llms_full_txt(content):
    """llms-full.txt (https://llmstxt.org/) — the fuller companion to
    llms.txt, for agents that fetch a single file rather than crawling:
    the complete body content of every page, not just links and one-line
    summaries. Reuses the same per-page Markdown builders as each page's
    own .md sibling, so there's one source of truth for "full content of
    this page" rather than a third copy that could drift."""
    t = content["en"]

    lines = [
        f"# {t['meta']['site_title']}",
        "",
        f"> {t['meta']['site_description']}",
        "",
        "Full content of every page on this site, for AI agents that fetch",
        "a single file rather than crawling. See /llms.txt for a shorter",
        "summary with links, or fetch any page directly with",
        "`Accept: text/markdown` for just that page.",
        "",
        "---",
        "",
        f"## {url_for(lang_facts_path('en'))}",
        "",
        build_markdown_facts(t),
        "",
        "---",
    ]

    for cs in t["case_studies"]:
        lines += [
            "",
            f"## {url_for(lang_case_study_path('en', cs['slug']))}",
            "",
            build_markdown_case_study(t, cs),
            "",
            "---",
        ]

    for article in t["resources"]["items"]:
        lines += [
            "",
            f"## {url_for(lang_resource_path('en', article['slug']))}",
            "",
            build_markdown_resource_article(t, article),
            "",
            "---",
        ]

    write("llms-full.txt", "\n".join(lines))


def write(rel_path, content):
    full = os.path.join(ROOT, rel_path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"wrote {rel_path}")


def main():
    content = load_content()
    legal_slugs = ("terms", "privacy", "impressum")

    for lang in LANGUAGES:
        code = lang["code"]
        t = content[code]

        home_alt = {l["code"]: lang_home_path(l["code"]) for l in LANGUAGES}
        build_index(t, code, home_alt)

        facts_alt = {l["code"]: lang_facts_path(l["code"]) for l in LANGUAGES}
        build_facts_page(t, code, facts_alt)

        n = len(t["case_studies"])
        for i, cs in enumerate(t["case_studies"]):
            prev_cs = t["case_studies"][(i - 1) % n]
            next_cs = t["case_studies"][(i + 1) % n]
            cs_alt = {l["code"]: lang_case_study_path(l["code"], cs["slug"]) for l in LANGUAGES}
            build_case_study(t, code, cs, prev_cs, next_cs, cs_alt)

        for slug in legal_slugs:
            legal_alt = {l["code"]: lang_legal_path(l["code"], slug) for l in LANGUAGES}
            build_legal(t, code, slug, legal_alt)

        resources_alt = {l["code"]: lang_resources_index_path(l["code"]) for l in LANGUAGES}
        build_resources_index(t, code, resources_alt)

        for article in t["resources"]["items"]:
            # Only link a language as an hreflang alternate if that language
            # actually has this slug — an article can go live in one
            # language before it's translated, and a real page has to exist
            # at the other end of every alternate link.
            article_alt = {
                l["code"]: lang_resource_path(l["code"], article["slug"])
                for l in LANGUAGES
                if any(a["slug"] == article["slug"] for a in content[l["code"]]["resources"]["items"])
            }
            build_resource_article(t, code, article, article_alt)

    build_404(content["en"])
    build_robots_sitemap(content)
    build_security_txt()
    build_manifest(content)
    build_llms_txt(content)
    build_llms_full_txt(content)
    print("\nBuild complete.")


if __name__ == "__main__":
    main()
