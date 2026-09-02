# Ricardo public-search viability reconnaissance

This is disposable technical research, not a Ricardo adapter or a recommendation
to operate a scraper. The policy notes below are observations, not legal advice.

## Tested

- Investigation date: 2026-09-02 (Europe/Madrid)
- Representative search:
  <https://www.ricardo.ch/de/s/omega%20seamaster/>
- Pagination samples:
  `?page=2` and `?page=3` only
- Access method: Python 3.13 standard-library `urllib`, first with its default
  User-Agent and then with an identifying, browser-shaped User-Agent
- Other surfaces inspected: server-rendered HTML, Next.js hydration data, public
  frontend bundles, the frontend search endpoint inferred from those bundles,
  two sampled listing pages, `robots.txt`, Ricardo's current terms, and Ricardo's
  public API/developer help pages
- Authentication, personal accounts, cookies, persisted sessions, proxies,
  fingerprint rotation, and browser automation were not used.

Run the experiment from the repository root:

```shell
python3 research/ricardo/search_experiment.py
```

It deliberately requests one page, extracts the first five results, and exits
with a clear error if the expected Next.js hydration structure or matching
server-rendered listing URLs disappear. `--page` and `--limit` exist only to
reproduce the small pagination samples; this is not a crawler.

## Findings

| Question | Finding |
| --- | --- |
| HTTP-only viable | **Yes**, for the public search result page |
| Browser required | **No** |
| Authentication required | **No** |
| Structured endpoint discovered | **Yes, but direct use was not viable**; see below |
| Stable listing IDs | **Yes** for a listing's observed lifetime; relisting behavior is unclear |
| Pagination understood | **Yes**, for the first three pages |
| Obvious anti-bot friction | **Medium** |
| Relevant public API/developer access found | **Yes**, but it requires Ricardo partnership credentials and an anonymous token |

### Access and rendering

The clean search URL returned a complete server-rendered result page. JavaScript
was not needed to obtain listings, and no cookie or session state was needed.
The HTML contained 60 listing cards as well as a structured Next.js/React Query
hydration payload with the same 60 records. There was no JSON-LD and no classic
`__NEXT_DATA__`; the data was carried in `self.__next_f.push(...)` flight data.

A bare Python `urllib` request received HTTP 403. Adding the single identifying
User-Agent used by the experiment returned HTTP 200. Three consecutive requests
with that User-Agent and three with an ordinary desktop-browser User-Agent all
returned complete pages without cookies or challenges. However, a `curl` request
with the research User-Agent received a Cloudflare managed challenge. Detail-page
checks were also inconsistent: the research User-Agent was challenged; with a
desktop-browser User-Agent one sampled listing returned 200 and a second returned
a Cloudflare 403. This was enough to confirm one extracted listing was live, but
also shows that access can depend on more than the URL and header string.

Cloudflare is clearly present (`server: cloudflare`, and challenged responses had
`cf-mitigated: challenge`). No CAPTCHA or throttling appeared during the small,
low-rate search-page sample. The experiment does not attempt to solve challenges.

### Data source

The easiest source is the hydration JSON already embedded in the HTTP response.
It is materially less ambiguous than parsing localized card text, but it is still
an undocumented Next.js implementation detail. The script uses server-rendered
anchor `href` values only to obtain canonical listing URLs, because the hydration
record itself did not contain a detail URL.

The current frontend bundle describes a GET request to:

```text
https://www.ricardo.ch/api/frontend/search/{encoded search term}
```

with parameters including `originalUrl`, `isMobile`, `nextPageOffset`,
`currentPage`, and `locale`. Direct unauthenticated requests to the inferred
endpoint returned HTTP 404 (`Cannot GET ...`), including with the current
`X-Client-Version`, XHR-like headers, and browser-like headers. It may be an
edge/internal path used differently during client navigation or a stale client
route. It is not a usable basis for this experiment. Fetching the HTML is simpler.

### Data available

The embedded records exposed:

- explicit decimal-string listing ID
- title
- auction/current bid price, buy-now price, bid count, and flags for auction and
  buy-now modes
- primary image URL
- condition key
- start, creation, and end timestamps
- shipping methods, costs, postcode, and city (a usable public location signal)
- category ID, brand, product-type key, offer capability, promotion/highlight,
  and MoneyGuard flags
- seller ID, but not seller display name or seller type in the search payload

The page and Ricardo UI use CHF, but currency was not repeated in each observed
hydration record. A consumer would therefore be relying on the Swiss marketplace
context or another page-level contract for currency.

### Pagination and identity

The public page uses `?page=N`. Pages 1, 2, and 3 were each retrievable directly
in a fresh stateless request. Each contained 60 records. The returned config was:

```text
page 1: pageSize=60, currentPage=1, nextOffset=60
page 2: pageSize=60, currentPage=2, nextOffset=118
page 3: pageSize=60, currentPage=3, nextOffset=177
backendPageLimit=1000
```

The representative query reported 454 total results during the final run. The
`backendPageLimit=1000` value is an observed frontend/backend configuration hint,
not a tested guarantee. No attempt was made to reach the final page or the limit.

IDs are explicit and are also the numeric suffix of listing URLs, for example
`...-1328439546/`. A promoted result with that same ID appeared on both page 1
and page 2, so deduplication must be by ID rather than result position. The
underlying ID did not vary across the duplicate. Ricardo's terms describe
automatic reactivation of some unsold offers, but this experiment did not
establish whether a reactivated or manually relisted offer retains its ID.

## Fragility

The experiment depends on all of the following:

1. Cloudflare continuing to allow this HTTP-client profile after a normal
   identifying User-Agent is supplied.
2. Ricardo continuing to server-render complete search results.
3. Next.js flight scripts retaining JSON-decodable `self.__next_f.push(...)`
   records containing a dehydrated query with `articles` and `config`.
4. Hydration field names such as `id`, `bidPrice`, and `hasAuction` remaining
   stable.
5. Server-rendered listing links keeping their `/de/a/{slug}-{id}/` shape.
6. CHF remaining a safe page/marketplace-level assumption.

This avoids CSS-class selectors and avoids a browser, but it is still coupled to
an undocumented web implementation. The Cloudflare inconsistency is the larger
operational risk. A production monitor would also need a policy-compliant answer
for pagination before relying on `?page=N`.

## Policy / access considerations

Ricardo's `robots.txt`, fetched on 2026-09-02, explicitly allows clean search
paths (`Allow: /*/s/`) for the general user agent. It also disallows search paths
with query strings (`Disallow: /*/s/*?`), which covers the observed `?page=N`
pagination, and disallows several internal API routes. Robots directives are not
an authorization statement, but the pagination rule is a clear negative
sustainability signal.

The current German terms (effective 2026-01-12), section 3.2, prohibit mechanisms,
software, or scripts that could disrupt correct site operation and measures that
could impose unreasonable or excessive infrastructure load. Section 3.7 limits
use of seller/offer-related information to the corresponding offer and forbids
advertising/newsletter use or passing it to third parties. The reviewed text did
not contain a blanket statement that every automated fetch is forbidden. Sherlock
should not infer permission from that absence.

Ricardo does publish developer documentation for a formal API. It documents a
`SearchService.SimpleSearch` method with page number/page size parameters and says
Search Service can be used with an anonymous token. “Anonymous” still requires a
partnership key/password to obtain the token, a signed usage agreement, initial
sandbox development, and contact with Ricardo for production credentials. The
documented API therefore looks like the most sustainable route worth discussing
with Ricardo, but it was outside this unauthenticated experiment and was not
tested.

Relevant public pages:

- <https://www.ricardo.ch/robots.txt>
- <https://help.ricardo.ch/hc/de/articles/4417210291858-Allgemeine-Gesch%C3%A4ftsbedingungen-AGB-g%C3%BCltig-ab-12-01-2026>
- <https://help.ricardo.ch/hc/de/articles/115002977185-Services>
- <https://help.ricardo.ch/hc/fr/articles/115002971329-How-to-perform-a-simple-search>
- <https://help.ricardo.ch/hc/de/articles/115002955709-Schnittstellen-Anbindung-entwickeln>
- <https://help.ricardo.ch/hc/de/articles/115002974805-Authentication>

## Verdict: YELLOW

Public search retrieval is surprisingly simple: one stateless HTTP request with
a normal User-Agent yields complete server-rendered cards and rich structured
records, so a browser prototype is unnecessary. It is not GREEN because the
contract is undocumented, Cloudflare behavior already varies by HTTP client and
page, and robots.txt disallows the query-string pagination needed for monitoring
beyond page 1. Ricardo **should receive a deeper prototype only if the next step
is to ask Ricardo about partnership API access and intended monitoring use**.
Absent that route, Sherlock should move to the next marketplace rather than invest
in hardening an unofficial scraper.
