#!/usr/bin/env python3
"""Static site generator for imenbouzouita.com.

No framework, no npm — just Python stdlib templating so the header/footer/
case-study template stay DRY while the deployed output is plain static
HTML/CSS/JS (GitHub Pages needs no build step at request time).

Run: python3 build.py
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.abspath(__file__))
SITE_URL = "https://imenbouzouita.com"
CALENDLY = "https://calendly.com/imenbouzouita/1-1-discovery-call"
FORMSPREE_ACTION = "https://formspree.io/f/xdenkldz"

NAV_LINKS = [
    ("What I Do", "#work-do"),
    ("Case Studies", "#work"),
    ("About", "#about"),
    ("Contact", "#contact"),
]


def rel(depth):
    """Path prefix to the site root from a page `depth` directories deep.

    Root-relative paths ("/assets/...") only work when the site is served
    from a domain root. GitHub Pages project sites are served under
    "/<repo-name>/", so everything here is generated relative instead —
    this makes the output work at any hosting depth (custom domain,
    project page, local preview) without changes.
    """
    return "../" * depth if depth else "./"

CASE_STUDIES = [
    {
        "slug": "conversion-engine",
        "title": "Conversion Engine",
        "one_liner": "Data-driven growth for a D2C e-commerce brand",
        "tag": "E-commerce",
        "role": "UX Audit & CRO",
        "timeline": "5 weeks",
        "focus": "Checkout & PDP",
        "tools": "Hotjar, GA4, Figma",
        "summary": "A direct-to-consumer retailer had healthy traffic and a leaking checkout. The brief was simple: find out where buyers were dropping off, and fix it without a full rebuild.",
        "sections": [
            ("The problem", "Paid traffic was converting well below category benchmarks, and the team couldn't tell whether the issue was pricing, trust, or friction. Every fix so far had been a guess."),
            ("The approach", "A structured audit combining session recordings, heatmaps, and a full funnel teardown — from ad landing to order confirmation — scored against conversion heuristics and prioritized by expected lift versus effort."),
            ("What shipped", "A ranked list of 22 fixes spanning checkout form design, shipping-cost transparency, and mobile PDP layout, plus three A/B tests to validate the highest-risk changes before a full rollout."),
            ("The outcome", "The team shipped the top-priority fixes within two sprints. Checkout abandonment and mobile bounce both moved in the right direction within the first month post-launch."),
        ],
    },
    {
        "slug": "frictionless-flow",
        "title": "Frictionless Flow",
        "one_liner": "Reimagining a B2B consultancy's digital presence",
        "tag": "B2B",
        "role": "Website Redesign",
        "timeline": "6 weeks",
        "focus": "IA & Positioning",
        "tools": "Webflow, Figma",
        "summary": "A B2B consultancy's site looked like every other consultancy's site — dense text, unclear positioning, no path from visitor to lead. The rebuild had to make the value proposition legible in one scroll.",
        "sections": [
            ("The problem", "Prospects were bouncing before reaching the services section. The existing IA buried differentiation under generic industry language, and there was no clear next step for a warm visitor."),
            ("The approach", "Stakeholder interviews to extract what actually made the firm different, followed by a full information architecture pass and a content-first wireframe before any visual design started."),
            ("What shipped", "A restructured site with a sharper homepage narrative, a services section organized around client outcomes instead of internal capabilities, and a single consistent lead-capture path."),
            ("The outcome", "Time on the services pages increased and the team reported clearer, better-qualified inbound conversations within the first quarter."),
        ],
    },
    {
        "slug": "neuroboost-ux",
        "title": "NeuroBoost UX",
        "one_liner": "Product optimization powered by neuroscience & eye-tracking",
        "tag": "UX Research",
        "role": "Neuro-UX Research",
        "timeline": "4 weeks",
        "focus": "Attention & Trust",
        "tools": "Eye-tracking, Tobii, Figma",
        "summary": "A product team suspected users weren't seeing their key trust signals, but standard usability testing wasn't showing why. This called for looking at attention itself, not just stated preference.",
        "sections": [
            ("The problem", "Self-reported feedback from usability tests kept contradicting the analytics — users said they noticed trust badges and guarantees, but conversion data suggested otherwise."),
            ("The approach", "Eye-tracking sessions layered over task-based usability testing, applying methods from training at the Deloitte Neuroscience Institute to separate what users say from what they actually attend to."),
            ("What shipped", "A gaze-pattern map of the key landing pages, revealing which trust elements were genuinely being seen, and a redesigned visual hierarchy that put the ignored signals where attention already was."),
            ("The outcome", "The redesigned hierarchy measurably shifted attention toward the intended trust signals in follow-up testing, giving the team evidence-backed confidence in the new layout."),
        ],
    },
    {
        "slug": "embedded-excellence",
        "title": "Embedded Excellence",
        "one_liner": "Scaling product delivery for automotive systems",
        "tag": "Automotive",
        "role": "Product Delivery",
        "timeline": "Ongoing",
        "focus": "Process & Tooling",
        "tools": "Jira, Figma, Design Systems",
        "summary": "An automotive systems team needed to ship embedded-software interfaces at a faster, more predictable pace without sacrificing the rigor the industry demands.",
        "sections": [
            ("The problem", "Design and engineering were working from disconnected specs, causing rework late in each cycle and making timelines hard to trust."),
            ("The approach", "Introduced a shared component system and a tighter design-to-dev handoff process, embedded directly with the delivery team rather than consulting from the outside."),
            ("What shipped", "A living design system aligned to the embedded UI constraints, plus a revised handoff workflow that caught inconsistencies before development started."),
            ("The outcome", "Rework dropped noticeably cycle over cycle, and the team could commit to delivery dates with far more confidence."),
        ],
    },
    {
        "slug": "admin-dash",
        "title": "Admin Dash",
        "one_liner": "A dashboard that makes analysts' daily work easier",
        "tag": "SaaS",
        "role": "Product Design",
        "timeline": "5 weeks",
        "focus": "Workflow Design",
        "tools": "Figma, Notion",
        "summary": "Internal analysts were spending more time fighting their own tooling than doing analysis. The dashboard had grown feature by feature with no one stepping back to ask how it was actually used.",
        "sections": [
            ("The problem", "Every new feature request had been bolted onto the existing dashboard, resulting in a cluttered interface that buried the handful of views analysts used daily."),
            ("The approach", "Contextual interviews with the analyst team to map actual daily workflows, followed by an information hierarchy rebuilt around frequency of use rather than feature completeness."),
            ("What shipped", "A redesigned dashboard with a task-oriented home view, saved filters for recurring reports, and a much shorter path to the three actions analysts performed most."),
            ("The outcome", "Analysts reported completing routine reporting tasks faster, and onboarding a new analyst became a same-day process instead of a multi-day one."),
        ],
    },
    {
        "slug": "citysense-mvp",
        "title": "CitySense MVP",
        "one_liner": "Smart-city pedestrian recognition, startup challenge",
        "tag": "Startup",
        "role": "Product & UX",
        "timeline": "3 weeks",
        "focus": "0-to-1 MVP",
        "tools": "Figma, Prototyping",
        "summary": "A startup challenge team had a strong technical concept for pedestrian-recognition smart-city infrastructure but no interface for the humans who'd actually operate it.",
        "sections": [
            ("The problem", "The core recognition technology worked, but there was no operator-facing interface, and the team was days away from a live pitch."),
            ("The approach", "Rapid MVP scoping to identify the single operator workflow worth building first, then a tight prototyping loop to get something testable in front of judges and early users."),
            ("What shipped", "A clickable MVP prototype covering the core monitoring workflow, built fast enough to leave time for rehearsal before the pitch."),
            ("The outcome", "The team presented a working interface alongside their technical demo instead of slides alone, and placed among the challenge's recognized teams."),
        ],
    },
    {
        "slug": "nap-grid",
        "title": "NAP Grid",
        "one_liner": "Simplifying new grid applications, end to end",
        "tag": "Energy",
        "role": "UX & Service Design",
        "timeline": "6 weeks",
        "focus": "Application Flow",
        "tools": "Figma, User Testing",
        "summary": "Applying for a new energy grid connection involved a paperwork-heavy process that confused applicants and generated avoidable support tickets for the utility's team.",
        "sections": [
            ("The problem", "Applicants regularly submitted incomplete or incorrect grid-connection requests, creating back-and-forth that slowed down every application and burdened support staff."),
            ("The approach", "Mapped the entire application journey end to end, identified exactly where applicants got confused, and redesigned the flow as a guided, step-by-step digital process."),
            ("What shipped", "A restructured application flow with inline guidance at the exact points where errors used to happen, plus clearer status communication after submission."),
            ("The outcome", "Incomplete submissions dropped and support tickets tied to application confusion fell noticeably in the months after launch."),
        ],
    },
]

TRUST_LOGOS = ["Siemens", "BMW", "Deloitte", "innogy", "und gretel", "TUM"]

CAPABILITIES = [
    {
        "title": "UX & CRO Audits",
        "pitch": "5 days, 15–30 prioritized fixes, zero fluff. I tell you exactly what's costing you conversions — and how to fix it.",
        "details": [
            "Full funnel teardown from entry to conversion",
            "Heatmaps, session recordings & analytics review",
            "Prioritized fix list scored by impact vs. effort",
            "Optional A/B test plan for the riskiest changes",
        ],
    },
    {
        "title": "Landing Page Redesign",
        "pitch": "From wireframe to live page in a week. Built to convert, not just to look nice.",
        "details": [
            "Conversion-first wireframes before visual design",
            "Copy tightened around a single clear action",
            "Mobile-first build, ready to launch in days",
            "Analytics baked in from day one",
        ],
    },
    {
        "title": "Full Website & Shop Builds",
        "pitch": "Webflow, Shopify, Framer, WordPress. Structure, design, and build — end to end.",
        "details": [
            "Information architecture & content strategy",
            "Custom visual design system",
            "Build on the platform that fits your team",
            "Handover docs so your team can self-serve after launch",
        ],
    },
    {
        "title": "Neuroscience-Backed Insights",
        "pitch": "Trained at the Deloitte Neuroscience Institute. I design with how people actually think, not just how they say they behave.",
        "details": [
            "Eye-tracking & attention mapping",
            "Behavioral heuristics applied to layout & copy",
            "Bridging what users say vs. what they do",
            "Evidence-backed design rationale for stakeholders",
        ],
    },
]

LANG_CHIPS = ["German", "English", "French", "Arabic"]
EXP_CHIPS = ["10+ years", "Deloitte", "Siemens", "BMW", "TU Munich"]


def esc(s):
    return s


def head(title, description, path="/", depth=0):
    og_url = f"{SITE_URL}{path}"
    base = rel(depth)
    return f"""<meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title}</title>
  <meta name="description" content="{description}" />
  <link rel="canonical" href="{og_url}" />
  <meta property="og:type" content="website" />
  <meta property="og:title" content="{title}" />
  <meta property="og:description" content="{description}" />
  <meta property="og:url" content="{og_url}" />
  <meta property="og:image" content="{SITE_URL}/assets/img/og-cover.jpg" />
  <meta name="twitter:card" content="summary_large_image" />
  <link rel="icon" href="{base}assets/img/favicon.svg" type="image/svg+xml" />
  <link rel="stylesheet" href="{base}assets/css/style.css" />
  <meta name="theme-color" content="#0E1B1F" />"""


def header_html(depth=0):
    base = rel(depth)
    links = "\n      ".join(
        f'<li><a href="{base}{href}">{label}</a></li>' for label, href in NAV_LINKS
    )
    return f"""<header class="site-header">
    <div class="container">
      <a href="{base}" class="logo" aria-label="Imen Bouzouita — home">Imen<span class="dot">.</span></a>
      <nav>
        <ul class="nav-links">
          {links}
          <li class="nav-cta"><a href="{CALENDLY}" class="btn btn-primary" target="_blank" rel="noopener">Book a call</a></li>
        </ul>
      </nav>
      <button class="nav-toggle" aria-label="Toggle menu" aria-expanded="false"><span></span></button>
    </div>
  </header>"""


def footer_html(depth=0):
    base = rel(depth)
    return f"""<footer class="site-footer">
    <div class="container">
      <div class="footer-top">
        <div>
          <a href="{base}" class="logo" aria-label="Imen Bouzouita — home">Imen<span class="dot">.</span></a>
        </div>
        <nav class="footer-nav">
          <a href="{base}#work-do">What I Do</a>
          <a href="{base}#work">Case Studies</a>
          <a href="{base}#about">About</a>
          <a href="{base}#contact">Contact</a>
        </nav>
        <div class="footer-social">
          <a href="https://instagram.com/" target="_blank" rel="noopener" aria-label="Instagram">IG</a>
          <a href="https://linkedin.com/" target="_blank" rel="noopener" aria-label="LinkedIn">in</a>
        </div>
      </div>
      <div class="footer-bottom">
        <span>&copy; {2026} Imen Bouzouita. All rights reserved.</span>
        <div class="legal-links">
          <a href="{base}terms.html">Terms</a>
          <a href="{base}privacy.html">Privacy</a>
          <a href="{base}impressum.html">Impressum</a>
        </div>
      </div>
    </div>
  </footer>"""


def page_shell(title, description, body, path="/", depth=0, extra_head=""):
    return f"""<!doctype html>
<html lang="en">
<head>
  {head(title, description, path, depth)}
  {extra_head}
</head>
<body>
  {header_html(depth)}
  {body}
  {footer_html(depth)}
  <script src="{rel(depth)}assets/js/main.js" defer></script>
</body>
</html>
"""


def build_index():
    trust_track = " ".join(f'<span class="trust-logo">{n}</span>' for n in TRUST_LOGOS)
    trust_track_full = trust_track + " " + trust_track  # duplicate for seamless marquee

    capability_cards = ""
    for i, cap in enumerate(CAPABILITIES, start=1):
        detail_items = "\n            ".join(f"<li>{d}</li>" for d in cap["details"])
        capability_cards += f"""
        <div class="capability-card" data-reveal>
          <span class="capability-index">0{i}</span>
          <h3>{cap['title']}</h3>
          <p>{cap['pitch']}</p>
          <details class="capability-detail">
            <summary>What's included</summary>
            <ul>
            {detail_items}
            </ul>
          </details>
        </div>"""

    work_cards = ""
    for cs in CASE_STUDIES:
        work_cards += f"""
        <a class="work-card" href="./work/{cs['slug']}/" data-reveal>
          <div class="cover" style="background: linear-gradient(140deg, var(--moonstone), var(--lilac)); position:absolute; inset:0; height:112%;"></div>
          <div class="work-card-body">
            <span class="work-tag">{cs['tag']}</span>
            <h3>{cs['title']}</h3>
            <p class="one-liner">{cs['one_liner']}</p>
            <span class="view-prompt">View project &rarr;</span>
          </div>
        </a>"""

    lang_chips = " ".join(f'<span class="chip">{c}</span>' for c in LANG_CHIPS)
    exp_chips = " ".join(f'<span class="chip accent">{c}</span>' for c in EXP_CHIPS[:1]) + \
                " ".join(f'<span class="chip">{c}</span>' for c in EXP_CHIPS[1:])

    body = f"""
  <main>
    <section class="hero">
      <div class="hero-blob b1" data-parallax="0.08"></div>
      <div class="hero-blob b2" data-parallax="0.15"></div>
      <div class="container hero-inner">
        <p class="eyebrow hero-eyebrow">Digital Product &middot; UX &middot; CRO Consultant &mdash; Berlin</p>
        <h1>Websites that look good and <em>actually work.</em></h1>
        <p class="lede">I help e-commerce, wellness, and SaaS brands turn browsers into buyers &mdash; with fast, research-backed UX audits and interfaces people actually want to use.</p>
        <div class="hero-ctas">
          <a href="{CALENDLY}" class="btn btn-primary" target="_blank" rel="noopener">Book a free discovery call</a>
          <a href="#work" class="btn-line">See the work &darr;</a>
        </div>
      </div>
      <div class="hero-scroll-hint">Scroll<span>&darr;</span></div>
    </section>

    <section class="trust-strip">
      <div class="container">
        <p class="label">10+ years turning traffic into revenue &mdash; trusted by teams at</p>
      </div>
      <div class="marquee"><div class="marquee-track">{trust_track_full}</div></div>
    </section>

    <section id="work-do">
      <div class="container">
        <div class="section-head" data-reveal>
          <p class="eyebrow">What I Do</p>
          <h2>Four ways to fix what's costing you customers.</h2>
        </div>
        <div class="capabilities-grid">{capability_cards}
        </div>
      </div>
    </section>

    <section id="work">
      <div class="container">
        <div class="section-head" data-reveal>
          <p class="eyebrow">Case Studies</p>
          <h2>Selected work.</h2>
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
            <source srcset="./assets/img/imen-portrait.webp" type="image/webp" />
            <img class="about-portrait" src="./assets/img/imen-portrait.jpg" alt="Portrait of Imen Bouzouita" loading="lazy" width="840" height="1120" />
          </picture>
        </div>
        <div class="about-text" data-reveal>
          <p class="eyebrow">About</p>
          <h2 class="on-dark" style="margin-block: 1rem 1.5rem;">Hi, I'm Imen.</h2>
          <p>I'm a digital product consultant based in Berlin, originally from Monastir. I've spent 10+ years moving between corporate innovation labs (Deloitte, Siemens, BMW) and scrappy freelance builds, which means I know how to make big-brand thinking work on a startup budget.</p>
          <p>I studied IT &amp; Electrical Engineering at TU Munich, trained in neuromarketing at the Deloitte Neuroscience Institute, and now spend my days auditing, designing, and building websites that don't just look good &mdash; they perform.</p>
          <p>Fluent in German, English, French and Arabic, and always up for a project that lets me build something a little different.</p>
          <div class="chip-row">{exp_chips}</div>
          <div class="chip-row">{lang_chips}</div>
          <img class="signature" src="./assets/img/logos/logo.png" alt="Imen Bouzouita signature" loading="lazy" />
        </div>
      </div>
    </section>

    <section id="contact">
      <div class="contact-section" data-reveal>
        <div class="container contact-inner">
          <div class="contact-grid">
            <div>
              <h2>Let's fix something.</h2>
              <p class="lede">Book a free discovery call and I'll review your homepage or shop on the spot &mdash; three actionable tips, no charge, no pitch.</p>
              <div class="hero-ctas mt-lg">
                <a href="{CALENDLY}" class="btn btn-primary" target="_blank" rel="noopener">Get 3 quick wins, free</a>
              </div>
              <p class="contact-secondary">Also open to Figma prototyping, AI-generated art, and full website/webshop builds on Webflow, Shopify, or Wix.</p>
            </div>
            <div>
              <form id="contact-form" action="{FORMSPREE_ACTION}" method="POST">
                <div class="form-field">
                  <label for="name">Name</label>
                  <input type="text" id="name" name="name" required />
                </div>
                <div class="form-field">
                  <label for="email">Email</label>
                  <input type="email" id="email" name="email" required />
                </div>
                <div class="form-field">
                  <label for="message">Message</label>
                  <textarea id="message" name="message" rows="4" required></textarea>
                </div>
                <button type="submit" class="btn btn-primary" style="width:100%; justify-content:center;">Send message</button>
                <p class="form-status" role="status"></p>
              </form>
            </div>
          </div>
        </div>
      </div>
    </section>
  </main>
"""
    html = page_shell(
        "Imen Bouzouita — Digital Product, UX & CRO Consultant, Berlin",
        "I help e-commerce, wellness, and SaaS brands turn browsers into buyers with research-backed UX audits and interfaces people actually want to use.",
        body,
        path="/",
        depth=0,
    )
    write("index.html", html)


CASE_TEMPLATE_EXTRA_CSS = ""


def build_case_study(cs, prev_cs, next_cs):
    sections_html = ""
    for heading, text in cs["sections"]:
        sections_html += f"<h2>{heading}</h2>\n        <p>{text}</p>\n        "

    body = f"""
  <main>
    <section class="page-hero">
      <div class="container">
        <div class="tag-row"><span class="work-tag" style="position:static;">{cs['tag']}</span></div>
        <p class="eyebrow">Case Study</p>
        <h1>{cs['title']}</h1>
        <p class="lede">{cs['one_liner']}</p>
        <div class="case-cover" data-reveal>
          <div style="width:100%; height:100%; display:flex; align-items:center; justify-content:center; color:rgba(14,27,31,0.35); font-family:var(--font-display);">Cover image placeholder</div>
        </div>
        <dl class="case-meta" data-reveal>
          <div><dt>Role</dt><dd>{cs['role']}</dd></div>
          <div><dt>Timeline</dt><dd>{cs['timeline']}</dd></div>
          <div><dt>Focus</dt><dd>{cs['focus']}</dd></div>
          <div><dt>Tools</dt><dd>{cs['tools']}</dd></div>
        </dl>
        <div class="case-body" data-reveal>
          <p class="lede" style="color: var(--ink);">{cs['summary']}</p>
          {sections_html}
        </div>
        <div class="case-nav">
          <a href="../{prev_cs['slug']}/" class="btn-line">&larr; {prev_cs['title']}</a>
          <a href="../../#work" class="btn btn-ghost">All work</a>
          <a href="../{next_cs['slug']}/" class="btn-line">{next_cs['title']} &rarr;</a>
        </div>
      </div>
    </section>
  </main>
"""
    html = page_shell(
        f"{cs['title']} — Case Study — Imen Bouzouita",
        cs["one_liner"],
        body,
        path=f"/work/{cs['slug']}/",
        depth=2,
    )
    write(f"work/{cs['slug']}/index.html", html)


def build_legal(slug, title, content_html):
    body = f"""
  <main>
    <section class="page-hero">
      <div class="container">
        <p class="eyebrow">Legal</p>
        <h1>{title}</h1>
        <div class="legal-content mt-lg">
          {content_html}
        </div>
      </div>
    </section>
  </main>
"""
    html = page_shell(f"{title} — Imen Bouzouita", f"{title} for imenbouzouita.com", body, path=f"/{slug}.html", depth=0)
    write(f"{slug}.html", html)


def build_legal_pages():
    build_legal(
        "terms",
        "Terms of Service",
        """
        <p>These terms govern the use of imenbouzouita.com and any consulting services booked through it. By using this site or booking a call, you agree to the terms below.</p>
        <h2>Services</h2>
        <p>UX audits, CRO reviews, landing page and website builds, and related consulting are scoped individually per engagement. Specific deliverables, timelines, and fees are confirmed in writing before work begins.</p>
        <h2>Discovery calls</h2>
        <p>Free discovery calls are offered as an introduction and light-touch review, not a substitute for a full audit or paid engagement.</p>
        <h2>Intellectual property</h2>
        <p>Deliverables produced under a paid engagement transfer to the client upon full payment, unless otherwise agreed in writing.</p>
        <h2>Liability</h2>
        <p>Recommendations are provided in good faith based on available data; outcomes depend on implementation and factors outside this consultancy's control.</p>
        <p><em>Placeholder terms &mdash; replace with your reviewed legal text before launch.</em></p>
        """,
    )
    build_legal(
        "privacy",
        "Privacy Policy",
        """
        <p>This site collects only what's needed to respond to enquiries: name, email, and message content submitted via the contact form, processed through Formspree. No analytics cookies are set without consent.</p>
        <h2>What's collected</h2>
        <ul>
          <li>Contact form submissions (name, email, message)</li>
          <li>Calendly booking details, handled under Calendly's own privacy policy</li>
        </ul>
        <h2>How it's used</h2>
        <p>Solely to respond to enquiries and manage booked calls. Data isn't sold or shared with third parties beyond the services required to operate this site (Formspree, Calendly).</p>
        <h2>Your rights</h2>
        <p>You can request access to or deletion of your data at any time by getting in touch via the contact form.</p>
        <p><em>Placeholder policy &mdash; replace with your reviewed legal text (GDPR-compliant, as required for a Berlin-based business) before launch.</em></p>
        """,
    )
    build_legal(
        "impressum",
        "Impressum",
        """
        <h2>Angaben gem&auml;&szlig; &sect; 5 TMG</h2>
        <p>Imen Bouzouita<br/>Mahlower Strasse 14<br/>12049 Berlin<br/>Deutschland</p>
        <h2>Kontakt</h2>
        <p>E-Mail: imenbouzouita@googlemail.com</p>
        <h2>Umsatzsteuer-ID</h2>
        <p>Umsatzsteuer-Identifikationsnummer gem&auml;&szlig; &sect; 27 a Umsatzsteuergesetz: DE367654068</p>
        <h2>Verantwortlich f&uuml;r den Inhalt nach &sect; 18 Abs. 2 MStV</h2>
        <p>Imen Bouzouita<br/>Mahlower Strasse 14<br/>12049 Berlin<br/>Deutschland</p>
        <h2>EU-Streitschlichtung</h2>
        <p>Die Europ&auml;ische Kommission stellt eine Plattform zur Online-Streitbeilegung (OS) bereit: <a href="https://ec.europa.eu/consumers/odr/" target="_blank" rel="noopener">https://ec.europa.eu/consumers/odr/</a></p>
        <h2>Verbraucherstreitbeilegung</h2>
        <p>Wir sind nicht bereit oder verpflichtet, an Streitbeilegungsverfahren vor einer Verbraucherschlichtungsstelle teilzunehmen.</p>
        """,
    )


def build_404():
    body = """
  <main>
    <section class="page-hero text-center">
      <div class="container">
        <p class="eyebrow" style="justify-content:center;">404</p>
        <h1>That page wandered off.</h1>
        <p class="lede">Even the best UX has a dead link now and then.</p>
        <div class="hero-ctas mt-lg" style="justify-content:center;">
          <a href="./" class="btn btn-primary">Back to home</a>
        </div>
      </div>
    </section>
  </main>
"""
    html = page_shell("Page not found — Imen Bouzouita", "Page not found.", body, path="/404.html", depth=0)
    write("404.html", html)


def build_robots_sitemap():
    write("robots.txt", f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n")

    urls = ["/", "/terms.html", "/privacy.html", "/impressum.html"] + [
        f"/work/{cs['slug']}/" for cs in CASE_STUDIES
    ]
    items = "\n".join(f"  <url><loc>{SITE_URL}{u}</loc></url>" for u in urls)
    sitemap = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{items}
</urlset>
"""
    write("sitemap.xml", sitemap)


def write(rel_path, content):
    full = os.path.join(ROOT, rel_path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w") as f:
        f.write(content)
    print(f"wrote {rel_path}")


def main():
    build_index()
    n = len(CASE_STUDIES)
    for i, cs in enumerate(CASE_STUDIES):
        prev_cs = CASE_STUDIES[(i - 1) % n]
        next_cs = CASE_STUDIES[(i + 1) % n]
        build_case_study(cs, prev_cs, next_cs)
    build_legal_pages()
    build_404()
    build_robots_sitemap()
    print("\nBuild complete.")


if __name__ == "__main__":
    main()
