/**
 * SEO / GEO / CRO Checker API — backend for the /tools/seo-checker/ widget.
 *
 * A Cloudflare Worker port of seo_geo_cro_checker.py (see
 * https://github.com/ — vendored copy at geo-checker-web/backend/). Same
 * ~60 checks, same check ids/severities/tips, so results stay comparable
 * with the Python CLI tool. Two deliberate departures from a literal port:
 *
 *   - HTML parsing uses Cloudflare's native HTMLRewriter instead of a
 *     hand-rolled parser, since Workers has no DOM/HTMLParser equivalent.
 *     HTMLRewriter is a real (lol-html) HTML parser, so <script>/<style>
 *     content is correctly excluded from generic text handlers without
 *     needing manual "skip depth" tracking the way the Python version did.
 *   - SSRF protection is hostname-pattern-based, not a real pre-fetch DNS
 *     resolution + private-IP check. Workers has no raw socket/DNS API, and
 *     more fundamentally: a Worker runs on Cloudflare's edge, which has no
 *     network path into any customer's private infrastructure to begin
 *     with (unlike a traditional VPS sitting inside a network) — so the
 *     classic SSRF-into-internal-network risk this guards against in the
 *     Python version is structurally much smaller here. This is still
 *     defense-in-depth, not a claimed equivalent guarantee.
 *
 * Deploy: Cloudflare dashboard -> Workers & Pages -> Create -> paste this
 * file's contents into the editor -> Deploy. Then:
 *   1. Create a KV namespace (Workers & Pages -> KV) and bind it to this
 *      worker as CHECKER_KV (Settings -> Variables -> KV Namespace Bindings).
 *   2. Add a secret PSI_API_KEY (Settings -> Variables -> Secrets) with a
 *      free Google PageSpeed Insights key:
 *      https://developers.google.com/speed/docs/insights/v5/get-started
 *   3. Bind a route: www.imenbouzouita.com/api/check* — more specific than
 *      the existing www.imenbouzouita.com/* route on
 *      markdown-negotiation-worker.js, so Cloudflare routes /api/check
 *      here and everything else still goes to that worker/GitHub Pages.
 */

// --------------------------------------------------------------------------
// Constants
// --------------------------------------------------------------------------

const USER_AGENT = "GEO-SEO-Checker/1.0 (+https://www.imenbouzouita.com/tools/seo-checker/; free audit tool)";
const FETCH_TIMEOUT_MS = 12_000;
// Cloudflare's own edge proxy generally closes a long-idle HTTP connection
// around 100s; staying well under that keeps a slow PSI response ending in
// our own clean AbortError handling below (a graceful, single-check "Low"
// failure) rather than a raw connection drop the visitor's browser can't
// explain.
const PSI_TIMEOUT_MS = 80_000;
const PSI_ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed";

const RATE_LIMIT_PER_HOUR = 5;
const CACHE_TTL_SECONDS = 900;

// Bots behind live AI answer/search surfaces: content they crawl can plausibly
// get cited or linked back to the source, so blocking them has a real
// visibility cost. Deliberately excludes training-only crawlers (CCBot,
// Bytespider, Amazonbot, etc.) that feed opaque downstream datasets with no
// citation/referral path back to the source — blocking those is a legitimate
// business choice, not a GEO mistake, so this tool doesn't check for them.
const AI_BOTS = [
  ["GPTBot", "OpenAI (ChatGPT) crawler"],
  ["OAI-SearchBot", "OpenAI ChatGPT Search crawler"],
  ["ClaudeBot", "Anthropic (Claude) crawler"],
  ["Google-Extended", "Google Gemini / AI Overviews training crawler"],
  ["PerplexityBot", "Perplexity crawler"],
  ["Applebot-Extended", "Apple Intelligence crawler"],
  ["meta-externalagent", "Meta AI crawler"],
];

// A short, static, human-readable name for every check — the frontend
// widget shows this as the primary heading of each result row, with the
// dynamic `detail` string underneath as a secondary explanation. Without
// this, two checks with similarly-worded dynamic detail text (e.g.
// cta_present's "Found 2 call-to-action element(s)..." vs
// cta_not_overwhelming's "2 call-to-action-style elements...") read as
// confusing duplicates in the UI — the CLI avoids this because it prints
// the check id as a prefix on every line, which the UI has no equivalent
// of without this map. Kept here (not in the vendored Python checker)
// since it's purely a presentation concern for this tool specifically,
// not part of the shared check logic.
const CHECK_LABELS = {
  http_reachable: "Page is reachable",
  https_used: "Served over HTTPS",
  html_parseable: "HTML parses correctly",
  robots_present: "robots.txt present",
  robots_not_blocking_all: "robots.txt isn't blocking all crawlers",
  sitemap_present: "Sitemap present",
  sitemap_referenced_in_robots: "Sitemap referenced in robots.txt",
  sitemap_has_lastmod: "Sitemap includes last-modified dates",
  meta_robots_indexable: "Page isn't set to noindex",
  canonical_present: "Canonical tag present",
  title_present: "Title tag present",
  title_length: "Title length is search-friendly",
  meta_description_present: "Meta description present",
  meta_description_length: "Meta description length is search-friendly",
  single_h1: "Exactly one H1 on the page",
  h1_has_text: "H1 contains real text",
  content_length: "Enough body content",
  image_alt_coverage: "Images have alt text",
  heading_hierarchy_sane: "Heading levels are sequential",
  html_lang_present: "Page language declared",
  charset_declared: "Character encoding declared",
  viewport_present: "Mobile viewport tag present",
  favicon_present: "Favicon present",
  semantic_content_wrapper: "Content wrapped in <main>/<article>",
  text_to_html_ratio: "Enough visible text vs. markup",
  og_title_present: "Open Graph title present",
  og_description_present: "Open Graph description present",
  og_image_present: "Open Graph preview image present",
  twitter_card_present: "Twitter/X card tag present",
  jsonld_present: "Structured data (JSON-LD) present",
  jsonld_valid: "Structured data is valid JSON",
  qa_schema_present: "FAQ/Q&A schema present",
  entity_schema_present: "Organization/Person schema present",
  author_signal_present: "Author byline signal present",
  llms_txt_present: "llms.txt present",
  llms_full_txt_present: "llms-full.txt present",
  freshness_headers_present: "Freshness headers (Last-Modified/ETag) present",
  ai_training_not_opted_out: "Not opted out of AI training",
  publish_date_signal: "Publish date signal present",
  cta_present: "Clear call-to-action present",
  cta_not_overwhelming: "Not too many competing CTAs",
  form_fields_labeled: "Form fields properly labeled",
  contact_info_present: "Contact info easy to find",
  trust_signals_present: "Trust signals present",
  skip_link_present: "Skip-to-content link present",
  external_links_rel_safe: "External links use rel=noopener",
  page_weight_reasonable: "Page weight is reasonable",
  nav_link_count_reasonable: "Primary navigation isn't overloaded",
  readability_reasonable: "Copy is easy to read",
  descriptive_link_text: "Link text is descriptive",
  interactive_elements_named: "Interactive elements have accessible names",
  no_duplicate_ids: "No duplicate id attributes",
  cwv_data_available: "Lighthouse data available",
  cwv_field_assessment: "Real-user Core Web Vitals rating",
  lcp_good: "Largest Contentful Paint is fast",
  cls_good: "Cumulative Layout Shift is low",
  responsiveness_good: "Page responds quickly to interaction",
  ttfb_good: "Server responds quickly (TTFB)",
  performance_score_good: "Lighthouse performance score is good",
};

function checkLabel(id) {
  if (CHECK_LABELS[id]) return CHECK_LABELS[id];
  const botMatch = AI_BOTS.find(([bot]) => id === `ai_bot_allowed_${bot.toLowerCase()}`);
  if (botMatch) return `${botMatch[0]} allowed to crawl`;
  return id;
}

const QA_SCHEMA_TYPES = new Set(["faqpage", "qapage", "howto"]);
const ENTITY_SCHEMA_TYPES = new Set(["organization", "website", "person"]);
const ARTICLE_SCHEMA_TYPES = new Set(["article", "blogposting", "newsarticle", "techarticle", "scholarlyarticle"]);
const AI_OPTOUT_TOKENS = new Set(["noai", "noimageai"]);

const CTA_KEYWORDS = [
  "buy now", "buy", "purchase", "add to cart", "add to bag", "sign up", "signup",
  "get started", "start free", "start your free trial", "try free", "try for free",
  "try now", "subscribe", "book a", "book now", "contact us", "request a demo",
  "request demo", "get a quote", "get quote", "download", "join now", "order now",
  "shop now", "start now", "get access", "reserve", "apply now", "learn more",
  "schedule a", "talk to sales", "get in touch",
];
const TRUST_KEYWORDS = ["testimonial", "review", "trusted by", "as seen in", "money-back", "money back", "guarantee"];
const GENERIC_LINK_TEXTS = new Set(["click here", "here", "read more", "more", "learn more", "this page", "link"]);

const SEVERITY_WEIGHT = { severe: 3, medium: 2, low: 1 };

// --------------------------------------------------------------------------
// Fetching
// --------------------------------------------------------------------------

async function fetchUrl(url, timeoutMs = FETCH_TIMEOUT_MS) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const resp = await fetch(url, {
      headers: { "User-Agent": USER_AGENT },
      redirect: "follow",
      signal: controller.signal,
    });
    const body = await resp.text();
    const headers = {};
    for (const [k, v] of resp.headers.entries()) headers[k.toLowerCase()] = v;
    return { ok: resp.ok, status: resp.status, finalUrl: resp.url || url, headers, body, error: resp.ok ? null : `HTTP ${resp.status}` };
  } catch (e) {
    return { ok: false, status: null, finalUrl: null, headers: {}, body: "", error: String(e && e.message || e) };
  } finally {
    clearTimeout(timer);
  }
}

async function fetchPageSpeedInsights(url, strategy, apiKey) {
  const params = new URLSearchParams({ url, strategy, category: "PERFORMANCE" });
  if (apiKey) params.set("key", apiKey);
  const endpoint = `${PSI_ENDPOINT}?${params.toString()}`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), PSI_TIMEOUT_MS);
  try {
    const resp = await fetch(endpoint, { headers: { "User-Agent": USER_AGENT }, signal: controller.signal });
    const data = await resp.json();
    if (!resp.ok) {
      const msg = (data && data.error && data.error.message) || `HTTP ${resp.status}`;
      return [null, msg];
    }
    return [data, null];
  } catch (e) {
    return [null, String(e && e.message || e)];
  } finally {
    clearTimeout(timer);
  }
}

// --------------------------------------------------------------------------
// HTML parsing (HTMLRewriter)
// --------------------------------------------------------------------------

/** Mirrors PageParser in the Python original, built from HTMLRewriter callbacks. */
function makePageState() {
  return {
    htmlLang: null,
    title: "",
    metas: [],
    links: [],
    h1s: [],
    h2s: [],
    h3s: [],
    images: [],
    jsonldBlocks: [],
    bodyWords: 0,
    bodyTextLen: 0,
    bodyTextSample: "",
    timeTags: [],
    hasMain: false,
    hasArticle: false,
    anchors: [],
    buttons: [],
    inputs: [],
    labelsFor: new Set(),
    navLinkCount: 0,
    allIds: [],
    // internal state
    _navDepth: 0,
    _primaryNavActive: false,
    _primaryNavClaimed: false,
    _labelDepth: 0,
    _jsonldBuf: "",
    _skipDepth: 0, // inside script/style/noscript — text there isn't visible body text
    _insideAnchor: false,
    _insideButton: false,
  };
}

function attrsToObject(element) {
  const out = {};
  for (const [name, value] of element.attributes) out[name] = value;
  return out;
}

class SimpleTextCollector {
  constructor(onChunk) {
    this.onChunk = onChunk;
  }
  text(chunk) {
    this.onChunk(chunk.text);
  }
}

async function parsePage(html) {
  const state = makePageState();

  const rewriter = new HTMLRewriter()
    .on("*", {
      element(el) {
        const id = el.getAttribute("id");
        if (id) state.allIds.push(id);
      },
    })
    .on("html", {
      element(el) {
        const lang = el.getAttribute("lang");
        if (lang) state.htmlLang = lang;
      },
    })
    .on("title", {
      element() { state.title = ""; },
      text(chunk) { state.title += chunk.text; },
    })
    .on("meta", {
      element(el) { state.metas.push(attrsToObject(el)); },
    })
    .on("link", {
      element(el) { state.links.push(attrsToObject(el)); },
    })
    .on("h1", {
      element() { state.h1s.push(""); },
      text(chunk) { if (state.h1s.length) state.h1s[state.h1s.length - 1] += chunk.text; },
    })
    .on("h2", {
      element() { state.h2s.push(""); },
      text(chunk) { if (state.h2s.length) state.h2s[state.h2s.length - 1] += chunk.text; },
    })
    .on("h3", {
      element() { state.h3s.push(""); },
      text(chunk) { if (state.h3s.length) state.h3s[state.h3s.length - 1] += chunk.text; },
    })
    .on("img", {
      element(el) {
        const attrs = attrsToObject(el);
        state.images.push(attrs);
        if ((attrs.alt || "").trim()) {
          if (state._insideAnchor && state.anchors.length) state.anchors[state.anchors.length - 1].has_accessible_img_alt = true;
          if (state._insideButton && state.buttons.length) state.buttons[state.buttons.length - 1].has_accessible_img_alt = true;
        }
      },
    })
    .on("main", {
      element() { state.hasMain = true; },
    })
    .on("article", {
      element() { state.hasArticle = true; },
    })
    .on("time", {
      element(el) { state.timeTags.push(attrsToObject(el)); },
    })
    .on("nav", {
      element(el) {
        state._navDepth += 1;
        if (!state._primaryNavClaimed && state._navDepth === 1) {
          state._primaryNavActive = true;
        }
        el.onEndTag(() => {
          if (state._navDepth > 0) {
            state._navDepth -= 1;
            if (state._navDepth === 0 && state._primaryNavActive) {
              state._primaryNavActive = false;
              state._primaryNavClaimed = true;
            }
          }
        });
      },
    })
    .on("a", {
      element(el) {
        const entry = {
          href: el.getAttribute("href") || "",
          rel: el.getAttribute("rel") || "",
          target: el.getAttribute("target") || "",
          aria_label: el.getAttribute("aria-label") || "",
          text: "",
        };
        state.anchors.push(entry);
        if (state._primaryNavActive) state.navLinkCount += 1;
        state._insideAnchor = true;
        el.onEndTag(() => { state._insideAnchor = false; });
      },
      text(chunk) {
        if (state.anchors.length) state.anchors[state.anchors.length - 1].text += chunk.text;
      },
    })
    .on("button", {
      element(el) {
        state.buttons.push({ text: "", aria_label: el.getAttribute("aria-label") || "" });
        state._insideButton = true;
        el.onEndTag(() => { state._insideButton = false; });
      },
      text(chunk) {
        if (state.buttons.length) state.buttons[state.buttons.length - 1].text += chunk.text;
      },
    })
    .on("label", {
      element(el) {
        state._labelDepth += 1;
        const forAttr = el.getAttribute("for");
        if (forAttr) state.labelsFor.add(forAttr);
        el.onEndTag(() => { if (state._labelDepth > 0) state._labelDepth -= 1; });
      },
    })
    .on("input, select, textarea", {
      element(el) {
        const entry = attrsToObject(el);
        entry.implicit_label = state._labelDepth > 0;
        state.inputs.push(entry);
        if (el.tagName === "input" && ["submit", "button"].includes((entry.type || "").toLowerCase())) {
          state.buttons.push({ text: entry.value || "" });
        }
      },
    })
    .on('script[type="application/ld+json"]', {
      element() { state._jsonldBuf = ""; },
      text(chunk) {
        state._jsonldBuf += chunk.text;
        if (chunk.lastInTextNode) {
          state.jsonldBlocks.push(state._jsonldBuf);
          state._jsonldBuf = "";
        }
      },
    })
    // Explicit skip-depth guard (mirrors the Python original) rather than
    // trusting that a generic "body" text handler naturally excludes
    // <script>/<style> content — belt-and-suspenders so raw JS/CSS source
    // can never leak into word counts, readability scoring, or CTA-text
    // matching.
    .on("script, style, noscript", {
      element(el) {
        state._skipDepth += 1;
        el.onEndTag(() => { if (state._skipDepth > 0) state._skipDepth -= 1; });
      },
    })
    .on("body", {
      text(chunk) {
        if (state._skipDepth > 0) return;
        const data = chunk.text;
        const words = data.match(/\w+/gu);
        if (words) state.bodyWords += words.length;
        state.bodyTextLen += data.replace(/\s+/g, " ").length;
        if (state.bodyTextSample.length < 20000) state.bodyTextSample += data;
      },
    });

  // HTMLRewriter only runs as it streams a response body — consume it fully
  // via .text() (we don't need the transformed HTML itself, just the side
  // effects captured into `state` above).
  const transformed = rewriter.transform(new Response(html, { headers: { "Content-Type": "text/html; charset=utf-8" } }));
  await transformed.text();

  return state;
}

function metaLookup(metas, { name, prop } = {}) {
  for (const m of metas) {
    const key = (m.name || "").toLowerCase();
    const pkey = (m.property || "").toLowerCase();
    if (name && key === name.toLowerCase()) return m.content;
    if (prop && pkey === prop.toLowerCase()) return m.content;
  }
  return null;
}

function linkLookup(links, rel) {
  for (const l of links) {
    const rels = (l.rel || "").toLowerCase().split(/\s+/);
    if (rels.includes(rel.toLowerCase())) return l;
  }
  return null;
}

function extractJsonLdInfo(blocks) {
  const types = new Set();
  let hasAuthor = false;
  let hasDatePublished = false;
  for (const block of blocks) {
    let data;
    try {
      data = JSON.parse(block);
    } catch {
      continue;
    }
    let nodes;
    if (Array.isArray(data)) nodes = data;
    else if (data && Array.isArray(data["@graph"])) nodes = data["@graph"];
    else if (data && typeof data === "object") nodes = [data];
    else nodes = [];
    for (const node of nodes) {
      if (!node || typeof node !== "object") continue;
      const t = node["@type"];
      if (typeof t === "string") types.add(t.toLowerCase());
      else if (Array.isArray(t)) t.forEach((x) => types.add(String(x).toLowerCase()));
      if ("author" in node) hasAuthor = true;
      if (node.datePublished) hasDatePublished = true;
    }
  }
  return { types, hasAuthor, hasDatePublished };
}

function isCtaText(text) {
  const t = text.trim().toLowerCase();
  if (!t || t.length > 60) return false;
  return CTA_KEYWORDS.some((kw) => t.includes(kw));
}

function countSyllables(word) {
  word = word.toLowerCase();
  const vowels = "aeiouy";
  let count = 0;
  let prevVowel = false;
  for (const ch of word) {
    const isVowel = vowels.includes(ch);
    if (isVowel && !prevVowel) count += 1;
    prevVowel = isVowel;
  }
  if (word.endsWith("e") && count > 1) count -= 1;
  return Math.max(1, count);
}

function fleschReadingEase(text) {
  const words = text.match(/[A-Za-z']+/g) || [];
  const wordCount = words.length || 1;
  const sentenceCount = (text.match(/[.!?]+/g) || []).length || 1;
  const syllableCount = words.reduce((sum, w) => sum + countSyllables(w), 0) || wordCount;
  return 206.835 - 1.015 * (wordCount / sentenceCount) - 84.6 * (syllableCount / wordCount);
}

// --------------------------------------------------------------------------
// robots.txt parsing
// --------------------------------------------------------------------------

function parseRobots(text) {
  const sitemaps = [];
  const groups = [];
  let currentAgents = [];
  let currentRules = [];
  let seenRuleSinceAgent = false;

  for (const rawLine of text.split("\n")) {
    const line = rawLine.split("#")[0].trim();
    if (!line || !line.includes(":")) continue;
    const idx = line.indexOf(":");
    const key = line.slice(0, idx).trim().toLowerCase();
    const val = line.slice(idx + 1).trim();

    if (key === "user-agent") {
      if (seenRuleSinceAgent) {
        groups.push([currentAgents, currentRules]);
        currentAgents = [];
        currentRules = [];
        seenRuleSinceAgent = false;
      }
      currentAgents.push(val.toLowerCase());
    } else if (key === "disallow" || key === "allow") {
      currentRules.push([key, val]);
      seenRuleSinceAgent = true;
    } else if (key === "sitemap") {
      sitemaps.push(val);
    }
  }
  if (currentAgents.length || currentRules.length) groups.push([currentAgents, currentRules]);
  return { sitemaps, groups };
}

function botAllowedRoot(groups, bot) {
  const botL = bot.toLowerCase();
  let matchedRules = null;
  for (const [agents, rules] of groups) {
    if (agents.includes(botL)) { matchedRules = rules; break; }
  }
  if (matchedRules === null) {
    for (const [agents, rules] of groups) {
      if (agents.includes("*")) { matchedRules = rules; break; }
    }
  }
  if (matchedRules === null) return true;
  const disallowAll = matchedRules.some(([k, v]) => k === "disallow" && v === "/");
  const allowOverride = matchedRules.some(([k, v]) => k === "allow" && (v === "/" || v === ""));
  return !(disallowAll && !allowOverride);
}

// --------------------------------------------------------------------------
// Checks
// --------------------------------------------------------------------------

async function runChecks(url, { skipVitals = false, psiApiKey = null, psiStrategy = "mobile" } = {}) {
  const results = [];
  const add = (id, category, severity, passed, detail, tip = "") => {
    results.push({ id, category, severity, passed, detail, tip });
  };

  const page = await fetchUrl(url);
  if (!page.ok && !page.body) {
    add("http_reachable", "Crawlability", "severe", false, `Request failed: ${page.error}`,
      "Make sure the URL is publicly reachable and returns a 2xx status.");
    return results;
  }
  add("http_reachable", "Crawlability", "severe", page.ok,
    page.ok ? `Fetched with status ${page.status}` : `Request failed: ${page.error}`,
    "Make sure the URL is publicly reachable and returns a 2xx status.");
  if (!page.ok) return results;

  add("https_used", "Crawlability", "severe", (page.finalUrl || url).toLowerCase().startsWith("https://"),
    `Final URL scheme: ${new URL(page.finalUrl || url).protocol.replace(":", "")}`,
    "Serve the site over HTTPS; most crawlers and AI systems downrank/ignore insecure pages.");

  let parser;
  try {
    parser = await parsePage(page.body);
  } catch (e) {
    add("html_parseable", "Crawlability", "severe", false, `HTML failed to parse: ${e && e.message}`);
    return results;
  }

  const parsedUrl = new URL(page.finalUrl || url);
  const root = `${parsedUrl.protocol}//${parsedUrl.host}`;
  const robotsRes = await fetchUrl(root + "/robots.txt");
  let robotsGroups = [];
  let robotsSitemaps = [];

  if (robotsRes.ok) {
    const parsed = parseRobots(robotsRes.body);
    robotsSitemaps = parsed.sitemaps;
    robotsGroups = parsed.groups;
    add("robots_present", "Crawlability", "medium", true, "robots.txt found");
    const starDisallowed = !botAllowedRoot(robotsGroups, "nonexistentbot-xyz");
    add("robots_not_blocking_all", "Crawlability", "severe", !starDisallowed,
      starDisallowed ? "robots.txt blocks all crawlers from '/'" : "robots.txt does not block general crawlers from '/'",
      "Remove a blanket 'Disallow: /' under 'User-agent: *' unless that is intentional.");
  } else {
    add("robots_present", "Crawlability", "medium", false, "robots.txt not found or unreachable",
      "Add a robots.txt file at the site root, even a permissive one, to guide crawlers.");
    add("robots_not_blocking_all", "Crawlability", "severe", true, "No robots.txt to block crawlers");
  }

  const sitemapUrl = robotsSitemaps[0] || root + "/sitemap.xml";
  const sitemapRes = await fetchUrl(sitemapUrl);
  const sitemapOk = sitemapRes.ok && (sitemapRes.body.includes("<urlset") || sitemapRes.body.includes("<sitemapindex"));
  add("sitemap_present", "Crawlability", "medium", sitemapOk,
    sitemapOk ? `Sitemap found at ${sitemapUrl}` : `No valid sitemap at ${sitemapUrl}`,
    "Publish a sitemap.xml and reference it via a 'Sitemap:' line in robots.txt.");
  add("sitemap_referenced_in_robots", "Crawlability", "low", robotsSitemaps.length > 0,
    robotsSitemaps.length ? "robots.txt references a sitemap" : "robots.txt has no Sitemap: directive",
    "Add 'Sitemap: https://yoursite.com/sitemap.xml' to robots.txt.");
  const sitemapHasLastmod = sitemapOk && sitemapRes.body.toLowerCase().includes("<lastmod");
  add("sitemap_has_lastmod", "Crawlability", "low", sitemapHasLastmod,
    sitemapHasLastmod ? "Sitemap entries include <lastmod> dates" : (sitemapOk ? "Sitemap has no <lastmod> dates" : "No sitemap to check"),
    "Add <lastmod> dates to sitemap entries so crawlers can prioritize freshly updated pages.");

  const metaRobots = (metaLookup(parser.metas, { name: "robots" }) || "").toLowerCase();
  const noindexed = metaRobots.includes("noindex");
  add("meta_robots_indexable", "Crawlability", "severe", !noindexed,
    metaRobots ? `meta robots = '${metaRobots}'` : "No meta robots tag (defaults to indexable)",
    "Remove 'noindex' from the meta robots tag if the page should be discoverable.");

  const canonical = linkLookup(parser.links, "canonical");
  add("canonical_present", "Crawlability", "medium", canonical !== null,
    canonical ? `canonical -> ${canonical.href}` : "No <link rel=canonical>",
    "Add a self-referencing canonical tag to avoid duplicate-content ambiguity.");

  const title = (parser.title || "").trim();
  add("title_present", "Content SEO", "severe", Boolean(title), title ? `Title: '${title}'` : "No <title>",
    "Add a descriptive <title> tag.");
  add("title_length", "Content SEO", "medium", title.length >= 10 && title.length <= 60,
    `Title length: ${title.length} chars`,
    "Keep the title roughly 10-60 characters so it isn't truncated in search results.");

  const description = metaLookup(parser.metas, { name: "description" }) || "";
  add("meta_description_present", "Content SEO", "severe", Boolean(description.trim()),
    description ? `Description: '${description.slice(0, 80)}...'` : "No meta description",
    "Add a meta description summarizing the page.");
  add("meta_description_length", "Content SEO", "medium",
    description.trim().length >= 50 && description.trim().length <= 160,
    `Description length: ${description.trim().length} chars`,
    "Aim for 50-160 characters so it isn't cut off in search snippets.");

  add("single_h1", "Content SEO", "medium", parser.h1s.length === 1, `Found ${parser.h1s.length} <h1> tag(s)`,
    "Use exactly one <h1> per page to signal the primary topic.");
  const h1Text = parser.h1s.length ? parser.h1s[0].trim() : "";
  add("h1_has_text", "Content SEO", "medium", Boolean(h1Text), h1Text ? `H1 text: '${h1Text}'` : "H1 is empty or missing",
    "Make sure the H1 contains meaningful text, not just an icon/image.");

  add("content_length", "Content SEO", "medium", parser.bodyWords >= 300, `~${parser.bodyWords} words of visible body text`,
    "Thin pages (<300 words) are less likely to be cited by AI answer engines or rank well.");

  if (parser.images.length) {
    const withAlt = parser.images.filter((img) => (img.alt || "").trim()).length;
    const pct = withAlt / parser.images.length;
    add("image_alt_coverage", "Content SEO", "medium", pct >= 0.8,
      `${withAlt}/${parser.images.length} images (${Math.round(pct * 100)}%) have alt text`,
      "Add descriptive alt text to images for accessibility and image search / AI captioning.");
  } else {
    add("image_alt_coverage", "Content SEO", "low", true, "No <img> tags found on the page");
  }

  const headingSane = !(parser.h3s.length && !parser.h2s.length);
  add("heading_hierarchy_sane", "Content SEO", "low", headingSane,
    headingSane ? "Heading levels look sequential" : "Found <h3> tags with no <h2> in between",
    "Avoid skipping heading levels (e.g. h1 straight to h3); a clean hierarchy helps AI parsers segment the document.");

  add("html_lang_present", "Technical", "low", Boolean(parser.htmlLang),
    parser.htmlLang ? `lang='${parser.htmlLang}'` : "No lang attribute on <html>",
    'Add a lang attribute (e.g. lang="en") to <html> to declare page language.');

  const charsetMeta = parser.metas.some((m) => "charset" in m) || (page.headers["content-type"] || "").includes("charset=");
  add("charset_declared", "Technical", "low", charsetMeta, charsetMeta ? "Charset declared" : "No charset declaration found",
    'Declare a charset via <meta charset="utf-8"> or the Content-Type header.');

  const viewport = metaLookup(parser.metas, { name: "viewport" });
  add("viewport_present", "Technical", "medium", Boolean(viewport), viewport ? `viewport: ${viewport}` : "No viewport meta tag",
    'Add <meta name="viewport" content="width=device-width, initial-scale=1"> for mobile rendering.');

  const favicon = linkLookup(parser.links, "icon") || linkLookup(parser.links, "shortcut icon");
  add("favicon_present", "Technical", "low", favicon !== null, favicon ? "Favicon linked" : "No favicon <link> found",
    'Add a <link rel="icon" ...> tag; missing favicons are a minor but common polish signal.');

  add("semantic_content_wrapper", "Technical", "low", parser.hasMain || parser.hasArticle,
    (parser.hasMain || parser.hasArticle) ? "Found <main> or <article> wrapper" : "No <main> or <article> tag found",
    "Wrap primary content in <main> or <article> so content extractors, including AI crawlers, can separate it from nav/boilerplate.");

  const htmlLen = page.body.length || 1;
  const textRatio = parser.bodyTextLen / htmlLen;
  add("text_to_html_ratio", "Technical", "medium", textRatio >= 0.10, `Visible text is ~${Math.round(textRatio * 100)}% of raw HTML size`,
    "A low text-to-HTML ratio usually means heavy JS/markup with little static content. Most AI crawlers don't execute JavaScript, so they see little to cite.");

  const ogTitle = metaLookup(parser.metas, { prop: "og:title" });
  const ogDesc = metaLookup(parser.metas, { prop: "og:description" });
  const ogImage = metaLookup(parser.metas, { prop: "og:image" });
  const twitterCard = metaLookup(parser.metas, { name: "twitter:card" });

  add("og_title_present", "Social", "low", Boolean(ogTitle), ogTitle || "No og:title",
    "Add Open Graph tags so links render nicely when shared.");
  add("og_description_present", "Social", "low", Boolean(ogDesc), ogDesc || "No og:description");
  add("og_image_present", "Social", "medium", Boolean(ogImage), ogImage || "No og:image",
    "Add an og:image so shared links show a preview thumbnail.");
  add("twitter_card_present", "Social", "low", Boolean(twitterCard), twitterCard || "No twitter:card tag");

  add("jsonld_present", "Structured Data", "medium", parser.jsonldBlocks.length > 0,
    parser.jsonldBlocks.length ? `${parser.jsonldBlocks.length} JSON-LD block(s) found` : "No JSON-LD found",
    "Add JSON-LD structured data (schema.org) so search engines and AI systems can parse entities/facts directly.");

  let validJsonld = 0;
  for (const block of parser.jsonldBlocks) {
    try { JSON.parse(block); validJsonld += 1; } catch { /* invalid */ }
  }
  if (parser.jsonldBlocks.length) {
    add("jsonld_valid", "Structured Data", "medium", validJsonld === parser.jsonldBlocks.length,
      `${validJsonld}/${parser.jsonldBlocks.length} JSON-LD blocks parse as valid JSON`,
      "Fix malformed JSON-LD; invalid blocks are ignored by parsers.");
  }

  const { types: jsonldTypes, hasAuthor: jsonldHasAuthor, hasDatePublished: jsonldHasDatePublished } = extractJsonLdInfo(parser.jsonldBlocks);

  const matchedQa = [...jsonldTypes].filter((t) => QA_SCHEMA_TYPES.has(t));
  add("qa_schema_present", "Structured Data", "medium", matchedQa.length > 0,
    matchedQa.length ? `Found schema types: ${matchedQa.sort().join(", ")}` : "No FAQPage/QAPage/HowTo schema found",
    "Add FAQPage or HowTo structured data around Q&A-style content so AI answer engines can lift direct answers.");

  const matchedEntity = [...jsonldTypes].filter((t) => ENTITY_SCHEMA_TYPES.has(t));
  add("entity_schema_present", "Structured Data", "low", matchedEntity.length > 0,
    matchedEntity.length ? `Found schema types: ${matchedEntity.sort().join(", ")}` : "No Organization/WebSite/Person schema found",
    "Add Organization or WebSite schema so AI systems can resolve who/what is behind the content (helps E-E-A-T).");

  const metaAuthor = metaLookup(parser.metas, { name: "author" });
  add("author_signal_present", "Structured Data", "low", Boolean(metaAuthor) || jsonldHasAuthor,
    (metaAuthor || jsonldHasAuthor) ? "Author signal found" : "No author/byline signal found",
    'Add a <meta name="author"> tag or an \'author\' field in JSON-LD; bylines help AI systems attribute and trust content.');

  const llmsRes = await fetchUrl(root + "/llms.txt");
  add("llms_txt_present", "GEO / AI Readiness", "medium", llmsRes.ok && Boolean(llmsRes.body.trim()),
    llmsRes.ok ? "llms.txt found" : "No llms.txt found",
    "Add an /llms.txt file summarizing your site for AI agents (see llmstxt.org).");

  const llmsFullRes = await fetchUrl(root + "/llms-full.txt");
  add("llms_full_txt_present", "GEO / AI Readiness", "low", llmsFullRes.ok && Boolean(llmsFullRes.body.trim()),
    llmsFullRes.ok ? "llms-full.txt found" : "No llms-full.txt found",
    "Consider an /llms-full.txt with fuller site content for AI agents that won't crawl deeply (see llmstxt.org).");

  const freshnessHeader = Boolean(page.headers["last-modified"] || page.headers["etag"]);
  add("freshness_headers_present", "GEO / AI Readiness", "low", freshnessHeader,
    freshnessHeader ? "Last-Modified/ETag header present" : "No Last-Modified or ETag header",
    "Serve a Last-Modified or ETag header so crawlers can detect content freshness without refetching the whole page.");

  const metaRobotsTokens = metaRobots ? new Set(metaRobots.split(",").map((t) => t.trim())) : new Set();
  const aiOptout = [...AI_OPTOUT_TOKENS].some((t) => metaRobotsTokens.has(t));
  add("ai_training_not_opted_out", "GEO / AI Readiness", "medium", !aiOptout,
    !aiOptout ? "No AI opt-out directive found" : "Found 'noai'/'noimageai' in meta robots",
    "Remove 'noai'/'noimageai' from meta robots if you want AI systems to use this content (support for this convention is inconsistent across engines).");

  for (const [bot, label] of AI_BOTS) {
    const allowed = robotsGroups.length ? botAllowedRoot(robotsGroups, bot) : true;
    add(`ai_bot_allowed_${bot.toLowerCase()}`, "GEO / AI Readiness", "severe", allowed,
      `${bot} (${label}) is ${allowed ? "allowed" : "BLOCKED"} by robots.txt`,
      `Remove any 'Disallow: /' rule under 'User-agent: ${bot}' if you want this AI system to cite your content.`);
  }

  const publishedTime = metaLookup(parser.metas, { prop: "article:published_time" });
  const hasTimeTag = parser.timeTags.length > 0;
  const hasDateSignal = Boolean(publishedTime) || hasTimeTag || jsonldHasDatePublished;
  const isArticlePage = [...jsonldTypes].some((t) => ARTICLE_SCHEMA_TYPES.has(t));
  if (isArticlePage) {
    add("publish_date_signal", "GEO / AI Readiness", "low", hasDateSignal,
      hasDateSignal ? "Publish date signal found" : "No published-date signal found on this article page",
      "Add an article:published_time meta tag, a <time datetime=...> element, or a 'datePublished' field in JSON-LD; freshness helps AI citation for article/content pages.");
  } else {
    add("publish_date_signal", "GEO / AI Readiness", "low", true,
      hasDateSignal ? "Publish date signal found" : "No published-date signal found — not applicable (page isn't marked as an Article/BlogPosting)");
  }

  const anchorTexts = parser.anchors.filter((a) => a.text).map((a) => a.text.trim());
  const buttonTexts = parser.buttons.filter((b) => b.text).map((b) => b.text.trim());
  const ctaMatches = [...anchorTexts, ...buttonTexts].filter(isCtaText);

  add("cta_present", "CRO / UX", "medium", ctaMatches.length > 0,
    ctaMatches.length ? `Found ${ctaMatches.length} call-to-action element(s), e.g. '${ctaMatches[0]}'` : "No clear call-to-action button/link text found",
    "Add a clear call-to-action (e.g. 'Get Started', 'Contact Us', 'Sign Up') so visitors know the next step.");
  add("cta_not_overwhelming", "CRO / UX", "low", ctaMatches.length <= 20, `${ctaMatches.length} call-to-action-style elements on the page`,
    "Too many competing CTAs can overwhelm visitors and dilute conversion; aim for one primary action per section.");

  const relevantInputs = parser.inputs.filter((i) => !["hidden", "submit", "button", "image", "reset"].includes((i.type || "text").toLowerCase()));
  if (relevantInputs.length) {
    let labeled = 0;
    for (const inp of relevantInputs) {
      const hasExplicit = Boolean(inp.id) && parser.labelsFor.has(inp.id);
      const hasAria = Boolean(inp["aria-label"] || inp["aria-labelledby"]);
      const hasPlaceholder = Boolean(inp.placeholder);
      const hasImplicit = inp.implicit_label === true;
      if (hasExplicit || hasAria || hasImplicit || hasPlaceholder) labeled += 1;
    }
    const pct = labeled / relevantInputs.length;
    add("form_fields_labeled", "CRO / UX", "medium", pct >= 0.8,
      `${labeled}/${relevantInputs.length} form field(s) (${Math.round(pct * 100)}%) have a label, aria-label, or placeholder`,
      "Give every form field a <label> (or aria-label); unlabeled fields confuse users and hurt form-completion rates.");
  } else {
    add("form_fields_labeled", "CRO / UX", "medium", true, "No form input fields found on the page");
  }

  const contactPresent = parser.anchors.some((a) => (a.href || "").toLowerCase().startsWith("tel:") || (a.href || "").toLowerCase().startsWith("mailto:"))
    || anchorTexts.some((t) => t.toLowerCase().includes("contact"));
  add("contact_info_present", "CRO / UX", "low", contactPresent, contactPresent ? "Contact link/info found" : "No contact link (tel:/mailto:/'contact') found",
    "Make it easy to reach you: add a visible contact link, phone number, or contact page.");

  const textSampleLower = parser.bodyTextSample.toLowerCase();
  const hasTrustSchema = [...jsonldTypes].some((t) => ["review", "aggregaterating"].includes(t));
  const hasTrustKeyword = TRUST_KEYWORDS.some((k) => textSampleLower.includes(k));
  add("trust_signals_present", "CRO / UX", "low", hasTrustSchema || hasTrustKeyword,
    (hasTrustSchema || hasTrustKeyword) ? "Trust/review signal found" : "No testimonials/reviews/trust signal detected",
    "Add testimonials, reviews, or trust badges; social proof measurably improves conversion rates.");

  const skipLink = parser.anchors.some((a) => (a.text || "").toLowerCase().includes("skip to") || ["#main", "#content", "#main-content"].includes(a.href || ""));
  add("skip_link_present", "CRO / UX", "low", skipLink, skipLink ? "Skip-to-content link found" : "No 'skip to content' link found",
    "Add a 'Skip to content' link as the first focusable element; it helps keyboard/screen-reader users reach content faster.");

  const externalBlankLinks = parser.anchors.filter((a) => (a.target || "").toLowerCase() === "_blank" && (a.href || "").toLowerCase().startsWith("http"));
  if (externalBlankLinks.length) {
    const safe = externalBlankLinks.filter((a) => (a.rel || "").toLowerCase().includes("noopener") || (a.rel || "").toLowerCase().includes("noreferrer")).length;
    const pct = safe / externalBlankLinks.length;
    add("external_links_rel_safe", "CRO / UX", "low", pct >= 0.8,
      `${safe}/${externalBlankLinks.length} target=_blank link(s) use rel=noopener/noreferrer`,
      'Add rel="noopener" to target="_blank" links; it stops the new tab from controlling your page and avoids a known performance/security anti-pattern.');
  } else {
    add("external_links_rel_safe", "CRO / UX", "low", true, "No target=_blank external links found");
  }

  add("page_weight_reasonable", "CRO / UX", "medium", htmlLen <= 300_000, `HTML document size: ${Math.round(htmlLen / 1024)} KB`,
    "Trim page weight (inline scripts/styles, markup bloat); heavier pages load slower and measurably hurt conversion.");

  add("nav_link_count_reasonable", "CRO / UX", "low", parser.navLinkCount ? parser.navLinkCount <= 12 : true,
    parser.navLinkCount ? `${parser.navLinkCount} link(s) in the primary <nav> (first one found on the page)` : "No <nav> element found",
    "Consider trimming primary navigation to a manageable set of choices; too many options can reduce conversion (paradox of choice). Note: only the first <nav> on the page is counted, since secondary/footer navs aren't the same first-choice decision for visitors.");

  const sampleWordCount = (parser.bodyTextSample.match(/[A-Za-z']+/g) || []).length;
  if (sampleWordCount >= 30) {
    const fre = fleschReadingEase(parser.bodyTextSample);
    add("readability_reasonable", "CRO / UX", "medium", fre >= 40, `Approx. Flesch Reading Ease score: ${Math.round(fre)} (higher = easier to read)`,
      "Simplify sentences and word choice; easier-to-read copy generally converts better for a general audience.");
  } else {
    add("readability_reasonable", "CRO / UX", "medium", true, "Not enough visible text to assess readability");
  }

  // ---- Accessibility ---------------------------------------------------
  const normalizeText = (t) => (t || "").replace(/\s+/g, " ").trim().toLowerCase().replace(/\.$/, "");

  const genericLinks = parser.anchors.filter((a) => (a.href || "").trim() && GENERIC_LINK_TEXTS.has(normalizeText(a.text)));
  add("descriptive_link_text", "Accessibility", "medium", genericLinks.length === 0,
    genericLinks.length ? `Found ${genericLinks.length} link(s) with generic text like 'click here'/'read more'` : "No generic/non-descriptive link text found",
    "Use descriptive link text (e.g. 'Download the 2024 report' instead of 'click here'); screen-reader users often navigate a page via a list of link text alone, out of surrounding context.");

  const hasAccessibleName = (entry) => Boolean(normalizeText(entry.text)) || Boolean((entry.aria_label || "").trim()) || entry.has_accessible_img_alt === true;

  const interactive = [...parser.anchors.filter((a) => !["", "#"].includes((a.href || "").trim())), ...parser.buttons];
  if (interactive.length) {
    const named = interactive.filter(hasAccessibleName).length;
    const pct = named / interactive.length;
    add("interactive_elements_named", "Accessibility", "severe", pct >= 0.9,
      `${named}/${interactive.length} interactive elements (${Math.round(pct * 100)}%) have an accessible name (visible text, aria-label, or alt text on an inner icon)`,
      "Give every link/button an accessible name. An icon-only control with no text, aria-label, or alt text on its icon is invisible to screen reader users, even though sighted users can see it.");
  } else {
    add("interactive_elements_named", "Accessibility", "severe", true, "No interactive links/buttons found");
  }

  const idCounts = new Map();
  for (const id of parser.allIds) {
    if (!id) continue;
    idCounts.set(id, (idCounts.get(id) || 0) + 1);
  }
  const duplicateIds = [...idCounts.entries()].filter(([, count]) => count > 1).map(([id]) => id).sort();
  add("no_duplicate_ids", "Accessibility", "medium", duplicateIds.length === 0,
    duplicateIds.length ? `Duplicate id attribute(s) found: ${duplicateIds.slice(0, 5).join(", ")}` : "No duplicate id attributes found",
    "Fix duplicate id attributes; they silently break <label for>, aria-describedby/aria-labelledby references, and in-page anchor links, since only the first matching element is ever used.");

  if (skipVitals) {
    add("cwv_data_available", "Core Web Vitals", "low", true, "Skipped");
  } else {
    const [psiData, psiError] = await fetchPageSpeedInsights(page.finalUrl || url, psiStrategy, psiApiKey);

    if (psiData === null) {
      add("cwv_data_available", "Core Web Vitals", "low", false, `PageSpeed Insights (Lighthouse) request failed: ${psiError}`,
        "PageSpeed Insights occasionally times out or briefly throttles requests, even with an API key configured. This check usually passes on a retry.");
    } else {
      add("cwv_data_available", "Core Web Vitals", "low", true, `Lighthouse data retrieved via PageSpeed Insights (${psiStrategy} strategy)`);

      const lh = psiData.lighthouseResult || {};
      const audits = lh.audits || {};
      const perfCategory = (lh.categories || {}).performance || {};
      const fieldExp = psiData.loadingExperience || {};
      const originExp = psiData.originLoadingExperience || {};
      const fieldMetrics = fieldExp.metrics || originExp.metrics || {};
      const overallCategory = fieldExp.overall_category || originExp.overall_category;

      if (overallCategory) {
        add("cwv_field_assessment", "Core Web Vitals", "severe", overallCategory === "FAST",
          `Real-user (CrUX field) Core Web Vitals assessment: ${overallCategory}`,
          "Google rates this URL's real-user Core Web Vitals below 'Good'. Prioritize the specific metric(s) flagged below (LCP, CLS, responsiveness).");
      } else {
        add("cwv_field_assessment", "Core Web Vitals", "low", true,
          "No real-user (CrUX) field data available for this URL — likely too little traffic; showing Lighthouse lab (simulated) metrics below instead");
      }

      const labMetric = (auditId) => (audits[auditId] || {}).numericValue;
      const fieldCategory = (metricKey) => (fieldMetrics[metricKey] || {}).category;

      const lcpMs = labMetric("largest-contentful-paint");
      const lcpFieldCat = fieldCategory("LARGEST_CONTENTFUL_PAINT_MS");
      if (lcpMs !== undefined || lcpFieldCat) {
        const good = lcpFieldCat ? lcpFieldCat === "FAST" : lcpMs <= 2500;
        let detail = lcpMs !== undefined ? `LCP: ${(lcpMs / 1000).toFixed(1)}s (lab)` : "LCP: field data only";
        if (lcpFieldCat) detail += ` — field: ${lcpFieldCat.toLowerCase()}`;
        add("lcp_good", "Core Web Vitals", "severe", good, detail,
          "Improve Largest Contentful Paint (target <=2.5s): optimize the hero image/text, server response time, and render-blocking resources.");
      }

      const clsVal = labMetric("cumulative-layout-shift");
      const clsFieldCat = fieldCategory("CUMULATIVE_LAYOUT_SHIFT_SCORE");
      if (clsVal !== undefined || clsFieldCat) {
        const good = clsFieldCat ? clsFieldCat === "FAST" : clsVal <= 0.1;
        let detail = clsVal !== undefined ? `CLS: ${clsVal.toFixed(2)} (lab)` : "CLS: field data only";
        if (clsFieldCat) detail += ` — field: ${clsFieldCat.toLowerCase()}`;
        add("cls_good", "Core Web Vitals", "severe", good, detail,
          "Reduce Cumulative Layout Shift (target <=0.1): set explicit width/height on images/embeds and avoid injecting content above existing content after load.");
      }

      const inpFieldCat = fieldCategory("INTERACTION_TO_NEXT_PAINT");
      const tbtMs = labMetric("total-blocking-time");
      if (inpFieldCat) {
        add("responsiveness_good", "Core Web Vitals", "severe", inpFieldCat === "FAST", `INP (field): ${inpFieldCat.toLowerCase()}`,
          "Improve Interaction to Next Paint (target <=200ms): break up long JavaScript tasks and reduce main-thread work triggered by user interactions.");
      } else if (tbtMs !== undefined) {
        add("responsiveness_good", "Core Web Vitals", "medium", tbtMs <= 200, `Total Blocking Time (lab proxy for responsiveness): ${Math.round(tbtMs)}ms`,
          "No real-user INP data is available, so this uses Total Blocking Time as a lab proxy. Reduce long JavaScript tasks to improve interaction responsiveness.");
      }

      const ttfbMs = labMetric("server-response-time");
      if (ttfbMs !== undefined) {
        add("ttfb_good", "Core Web Vitals", "medium", ttfbMs <= 800, `Server response time (TTFB, lab): ${Math.round(ttfbMs)}ms`,
          "Reduce Time to First Byte (target <=800ms): use caching, a CDN, or faster server-side processing.");
      }

      const perfScore = perfCategory.score;
      if (perfScore !== undefined && perfScore !== null) {
        add("performance_score_good", "Core Web Vitals", "medium", perfScore * 100 >= 50,
          `Lighthouse performance score: ${Math.round(perfScore * 100)}/100 (${psiStrategy})`,
          "Aim for a Lighthouse performance score of 90+; review the Lighthouse report's opportunities and diagnostics for the biggest wins.");
      }
    }
  }

  return results;
}

// --------------------------------------------------------------------------
// Scoring
// --------------------------------------------------------------------------

function grade(pct) {
  if (pct >= 90) return "A";
  if (pct >= 80) return "B";
  if (pct >= 70) return "C";
  if (pct >= 50) return "D";
  return "F";
}

function score(results) {
  const totalWeight = results.reduce((sum, r) => sum + SEVERITY_WEIGHT[r.severity], 0);
  const earnedWeight = results.filter((r) => r.passed).reduce((sum, r) => sum + SEVERITY_WEIGHT[r.severity], 0);
  const pct = totalWeight ? (earnedWeight / totalWeight) * 100 : 0;
  const passedCount = results.filter((r) => r.passed).length;
  return { pct, passedCount, total: results.length };
}

function toJson(url, results) {
  const { pct, passedCount, total } = score(results);
  return {
    url,
    score_pct: Math.round(pct * 10) / 10,
    grade: grade(pct),
    passed: passedCount,
    total,
    checks: results.map((r) => ({ id: r.id, label: checkLabel(r.id), category: r.category, severity: r.severity, passed: r.passed, detail: r.detail, tip: r.tip })),
  };
}

// --------------------------------------------------------------------------
// SSRF-lite validation
// --------------------------------------------------------------------------

const PRIVATE_HOST_PATTERNS = [
  /^localhost$/i,
  /^127\./,
  /^10\./,
  /^172\.(1[6-9]|2\d|3[01])\./,
  /^192\.168\./,
  /^169\.254\./,
  /^0\.0\.0\.0$/,
  /^::1$/,
  /^\[::1\]$/,
  /\.local$/i,
  /^metadata\.google\.internal$/i,
];

function isPublicHttpUrl(rawUrl) {
  let parsed;
  try {
    parsed = new URL(rawUrl);
  } catch {
    return [false, "Could not parse URL"];
  }
  if (!["http:", "https:"].includes(parsed.protocol)) return [false, "Only http/https URLs are allowed"];
  if (!parsed.hostname) return [false, "URL has no hostname"];
  const hostname = parsed.hostname.toLowerCase();
  if (PRIVATE_HOST_PATTERNS.some((re) => re.test(hostname))) return [false, "URL resolves to a non-public address"];
  return [true, ""];
}

// --------------------------------------------------------------------------
// Worker entry point
// --------------------------------------------------------------------------

function clientIp(request) {
  return request.headers.get("CF-Connecting-IP") || request.headers.get("X-Forwarded-For") || "unknown";
}

async function isRateLimited(kv, ip) {
  const key = `rl:${ip}`;
  const raw = await kv.get(key);
  const count = raw ? parseInt(raw, 10) : 0;
  if (count >= RATE_LIMIT_PER_HOUR) return true;
  await kv.put(key, String(count + 1), { expirationTtl: 3600 });
  return false;
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname !== "/api/check") {
      return new Response("Not found", { status: 404 });
    }
    if (request.method !== "POST") {
      return new Response(JSON.stringify({ error: "Method not allowed" }), { status: 405, headers: { "Content-Type": "application/json" } });
    }

    const ip = clientIp(request);
    if (env.CHECKER_KV) {
      const limited = await isRateLimited(env.CHECKER_KV, ip);
      if (limited) {
        return new Response(JSON.stringify({ error: "Rate limit exceeded. Please try again later." }), {
          status: 429, headers: { "Content-Type": "application/json" },
        });
      }
    }

    let data;
    try {
      data = await request.json();
    } catch {
      data = {};
    }
    let rawUrl = (data.url || "").trim();
    if (!rawUrl) {
      return new Response(JSON.stringify({ error: "Missing 'url'" }), { status: 400, headers: { "Content-Type": "application/json" } });
    }
    if (rawUrl.length > 2048) {
      return new Response(JSON.stringify({ error: "URL too long" }), { status: 400, headers: { "Content-Type": "application/json" } });
    }
    if (!rawUrl.includes("://")) rawUrl = "https://" + rawUrl;

    const [ok, reason] = isPublicHttpUrl(rawUrl);
    if (!ok) {
      return new Response(JSON.stringify({ error: `Invalid URL: ${reason}` }), { status: 400, headers: { "Content-Type": "application/json" } });
    }

    const cacheKey = `cache:${rawUrl.toLowerCase().replace(/\/$/, "")}`;
    if (env.CHECKER_KV) {
      const cached = await env.CHECKER_KV.get(cacheKey, "json");
      if (cached) {
        return new Response(JSON.stringify(cached), { headers: { "Content-Type": "application/json" } });
      }
    }

    const results = await runChecks(rawUrl, { psiApiKey: env.PSI_API_KEY || null });
    const payload = toJson(rawUrl, results);

    if (env.CHECKER_KV) {
      await env.CHECKER_KV.put(cacheKey, JSON.stringify(payload), { expirationTtl: CACHE_TTL_SECONDS });
    }

    return new Response(JSON.stringify(payload), { headers: { "Content-Type": "application/json" } });
  },
};
