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
            'content-signal': 'ai-train=yes, search=yes, ai-input=yes',
          },
        });
      }
      // No .md sibling for this path (e.g. /de/, a legal page) — fall
      // through and serve the normal HTML response below instead.
    }

    const response = await fetch(request);
    const headers = new Headers(response.headers);
    headers.set('Vary', 'Accept');
    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers,
    });
  },
};
