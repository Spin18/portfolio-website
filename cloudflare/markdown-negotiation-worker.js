/**
 * Markdown-for-agents content negotiation, without Cloudflare's paid
 * "Markdown for Agents" feature.
 *
 * build.py already generates a clean .md sibling next to every case study
 * and Resources article's index.html (and the homepage's content is
 * already summarised at /llms.txt). This Worker is the missing piece:
 * true same-URL negotiation on the `Accept` header, so an agent can
 * request the exact page URL with `Accept: text/markdown` and get the
 * .md content back directly, while a normal browser request for the same
 * URL still gets the regular HTML untouched.
 *
 * Deploy: Cloudflare dashboard -> Workers & Pages -> Create -> paste this
 * file's contents into the editor -> Deploy. Then bind it to the zone:
 * Workers & Pages -> your worker -> Settings -> Domains & Routes -> Add
 * route -> route pattern `www.imenbouzouita.com/*`, matching this zone.
 *
 * No Wrangler/Node install needed — this site has no npm toolchain, and
 * the dashboard editor is sufficient for a worker this small.
 */

// Content-Security-Policy for the whole zone. Verified empirically against
// the live site's actual third-party network calls (GA4, Contentsquare,
// Cloudflare Web Analytics, Formspree) rather than guessed:
//   - script-src needs no 'unsafe-inline': the one inline event handler
//     that used to require it (the async font-swap trick) was refactored
//     into assets/js/main.js.
//   - style-src still needs 'unsafe-inline': the whole stylesheet is
//     inlined into every page's <head>, plus several inline style="..."
//     attributes. Rewriting all of that to avoid it is a much bigger,
//     riskier change for a low-severity threat class (CSS injection, not
//     arbitrary code execution) — not worth it here.
//   - connect-src/script-src use https://*.contentsquare.net (not just
//     t.contentsquare.net) since Contentsquare's collection traffic goes
//     to a second subdomain (c.ba.contentsquare.net) and may use others
//     for session recording that weren't observed in one test session.
//   - Deliberately NOT allowing the GA4 "Google signals"/ads-audiences
//     ping (a per-visitor-country google.<tld>/ads/ga-audiences request,
//     loaded as a tracking pixel via img-src): it's an ads-remarketing
//     signal unrelated to core pageview tracking (which uses the stable
//     analytics.google.com), the site runs no Google Ads, and the
//     destination domain varies by country so it can't be allowlisted
//     completely anyway. Blocking it is a privacy positive, not a
//     functional loss.
//   - Cloudflare itself (not our own code) injects a small inline
//     <script>window.__CF$cv$params={...}</script> on every page for its
//     own challenge-platform/bot-management feature. Its content (and
//     hence its hash) rotates on some cadence — confirmed by seeing two
//     different hashes across two test sessions a few minutes apart —
//     so hash-pinning isn't viable (it would need constant, reactive
//     updates and silently break the challenge platform for real
//     visitors in between fixes). 'unsafe-inline' is accepted here as
//     the practical choice; note it only permits *inline* script
//     execution, external <script src> is still restricted to the
//     domains listed below.
// Verified in Report-Only mode against real traffic (GA4, Contentsquare,
// Cloudflare Web Analytics, Formspree all confirmed working) before
// switching to this enforcing header.
const CSP = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline' https://static.cloudflareinsights.com https://www.googletagmanager.com https://*.contentsquare.net",
  "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
  "font-src 'self' https://fonts.gstatic.com",
  "img-src 'self' data:",
  "connect-src 'self' https://formspree.io https://analytics.google.com https://*.google-analytics.com https://*.contentsquare.net https://cloudflareinsights.com",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self' https://formspree.io",
  "frame-ancestors 'self'",
  "upgrade-insecure-requests",
].join('; ');

// Other standard security headers, applied zone-wide alongside CSP.
// All low-risk/no compatibility surprises (unlike CSP, none of these
// needed empirical Report-Only testing):
//   - HSTS was previously max-age=0 (a leftover from the original domain
//     migration that actively told browsers to stop enforcing HTTPS) —
//     replaced with a real policy. No "preload" flag: that requires
//     submission to hstspreload.org and is hard to reverse once shipped
//     in browsers, a bigger commitment than fixing the header itself.
//   - X-Frame-Options is redundant with CSP's frame-ancestors 'self' for
//     modern browsers, kept as a fallback for older ones that don't
//     support frame-ancestors.
const SECURITY_HEADERS = {
  'Content-Security-Policy': CSP,
  'X-Content-Type-Options': 'nosniff',
  'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
  'X-Frame-Options': 'SAMEORIGIN',
  'Referrer-Policy': 'strict-origin-when-cross-origin',
  'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
  'Cross-Origin-Opener-Policy': 'same-origin',
  // Verified in Report-Only mode first: GA4, Contentsquare, the
  // Cloudflare beacon, and Google Fonts (CSS + font files) all already
  // send Cross-Origin-Resource-Policy: cross-origin. The Formspree
  // contact-form fetch() doesn't send that header, but doesn't need to —
  // confirmed empirically (response type "cors" with a valid
  // Access-Control-Allow-Origin) that fetch()'s default CORS mode
  // satisfies require-corp on its own, independent of CORP headers.
  'Cross-Origin-Embedder-Policy': 'require-corp',
};

export default {
  async fetch(request) {
    const accept = request.headers.get('Accept') || '';
    const wantsMarkdown = accept.includes('text/markdown');
    const url = new URL(request.url);

    // Every path on this site that has a .md sibling is directory-style
    // (ends in "/"): the homepage, and every work/<slug>/ and
    // resources/<slug>/ page, in both languages. Anything else (the
    // .html legal pages, assets, etc.) has no sibling, so it's left
    // alone entirely — the branch below just won't find one and will
    // fall through to the normal HTML response.
    if (wantsMarkdown && url.pathname.endsWith('/')) {
      const mdPath = url.pathname === '/' ? '/llms.txt' : `${url.pathname}index.md`;
      const mdResponse = await fetch(new URL(mdPath, url.origin));

      if (mdResponse.ok) {
        return new Response(mdResponse.body, {
          status: 200,
          headers: {
            'Content-Type': 'text/markdown; charset=utf-8',
            'Vary': 'Accept',
            'content-signal': 'search=yes, ai-input=yes, ai-train=no',
            ...SECURITY_HEADERS,
          },
        });
      }
      // No .md sibling for this path (e.g. /de/, a legal page) — fall
      // through and serve the normal HTML response below instead.
    }

    const response = await fetch(request);
    const headers = new Headers(response.headers);
    headers.set('Vary', 'Accept');
    for (const [name, value] of Object.entries(SECURITY_HEADERS)) {
      headers.set(name, value);
    }
    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers,
    });
  },
};
