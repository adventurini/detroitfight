# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Marketing site for Detroit Fight Company, a combat sports gym in Winter Springs, FL. Hand-written static HTML deployed on Vercel from `main` (repo: `adventurini/detroitfight`, live at https://detroitfight.com).

There is no build step, no package manager, no dependencies, no tests, and no linter. Every page is a single self-contained `.html` file with its CSS in an inline `<style>` block and its JS in a `<script>` block before `</body>`.

## Local development

```powershell
powershell -File .dev-server.ps1   # serves the repo root at http://127.0.0.1:3000/
```

The dev server is a ~40-line `HttpListener` that maps URL path → file on disk. It does **not** emulate Vercel's `cleanUrls`, so extensionless links in the markup 404 locally — browse `/boxing.html`, not `/boxing`. Only the root `/` is special-cased to `index.html`.

Deploy = push to `main`. There is no staging environment.

## Architecture: duplication is the design

Each page independently repeats the CSS reset, `:root` design tokens, nav markup, mobile-nav toggle script, footer, and analytics snippet. The content pages are 1,200–1,950 lines each and are ~70% shared boilerplate.

**Any change to shared chrome must be applied to every page by hand.** That includes: nav links, footer, design tokens, GA snippet, and the scroll/mobile-menu scripts. Grep for the pattern across `*.html` and edit each hit — there is no partial/include mechanism to reach for, and introducing a build step is a much larger change than the site currently warrants.

Design tokens live in a per-page `:root`: `--deep-black #0A0A0A` (page bg), `--black #1A1A1A` (cards), `--green #7D9B76` (accent/CTA), `--white`, `--grey #D8D8D8`. Type is Bebas Neue (headings, uppercase, letter-spaced) and Barlow Condensed (body), loaded from Google Fonts on every page. Note `thank-you.html` uses stale variable *names* from an earlier red palette (`--red`, `--gold`) that are now assigned green values — don't "fix" the values to match the names.

## Page roles

- **Content pages** (`index`, `jiu-jitsu`, `boxing`, `muay-thai`, `coaches`, `schedule`, `pricing`, `the-gym`, `free-trial`) — full site chrome, in the nav and sitemap.
- **`lp.html`** — standalone Google Ads landing page. Deliberately minimal: no nav, no footer, no site CSS, system font stack for the body, a daily-resetting countdown, and a GoHighLevel form iframe. Not in the nav or sitemap. Optimized for load speed; keep it that way when editing.
- **`thank-you.html`** — post-conversion page, `noindex, nofollow`, and the only page carrying the Google Ads tag. Contains an intentional `[PLACEHOLDER: ...]` block for follow-up timing copy awaiting agency input.
- **`privacy-policy.html`, `terms.html`** — legal, minimal chrome.
- **`googled018ab236e6d501f.html`** — Google Search Console verification. Leave alone.

## Routing

`vercel.json` sets `cleanUrls: true`, so all internal links use extensionless paths (`/boxing`, `/free-trial`). It also holds permanent redirects for retired routes (`/camp`, `/kids-camp` → `/`) and canonicalization (`/index.html` → `/`, `/privacy-policy.html` → `/privacy-policy`). New pages need a sitemap entry; retired pages need a redirect here, not just a deletion.

On `index.html` the logo and Home link point at `#home` (the page has in-page anchor sections); on every other page they point at `/`.

## Lead capture and tracking

Three separate paths, all feeding GoHighLevel — don't assume one covers the others:

1. **`free-trial.html`** — hand-rolled form (`#dfc-booking-form`) that `POST`s JSON directly to a LeadConnector webhook. Has a honeypot input `website_url_hp`, fires `gtag('event','generate_lead')` on success, and swaps the form for an inline confirmation (it does **not** redirect to `/thank-you`). On failure it alerts with the phone number.
2. **`lp.html`** — GoHighLevel form iframe (`form_embed.js`); redirect-to-thank-you is configured in GHL, not in this repo.
3. **Schedule/booking embeds** — Gymdesk `widgets.js` with gym id `6zgd3`, embedded on most content pages.

Analytics: GA4 `G-KYCVH9837V` in the `<head>` of every content page; Google Ads `AW-18094262765` **only** on `thank-you.html`. A Meta Pixel block is commented out on `index.html` and `thank-you.html` pending a pixel ID.

## SEO surface

This site was built to be read by search engines and AI crawlers, and several files must stay in sync when content changes:

- `sitemap.xml` — manual list of the extensionless canonical URLs with `lastmod`.
- `robots.txt` — explicitly allows GPTBot, OAI-SearchBot, ChatGPT-User, ClaudeBot, Claude-Web, PerplexityBot, Google-Extended.
- `llms.txt` — plain-language summary of location, programs, pricing, and key URLs for LLM consumers.
- Per-page `<head>`: canonical, Open Graph, and Twitter card tags.
- Per-page inline JSON-LD: `LocalBusiness` + `Service` + `BreadcrumbList` on program pages, `FAQPage` on `index`, `Person` on `coaches`, `Offer`/`UnitPriceSpecification` on `pricing`.

## Business facts repeated across files

Changing any of these means grepping the whole repo, including `llms.txt`, JSON-LD blocks, and meta descriptions:

- Address: 1425 Tuskawilla Rd #209, Winter Springs, FL 32708
- Phone: (407) 696-6969 · Email: sean@detroitfight.com
- Pricing: a single $199/mo All Access Membership, no contracts
- Offer: free trial class (the current site-wide CTA language)
