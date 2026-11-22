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

Design tokens live in a per-page `:root`: `--deep-black #0A0A0A` (page bg), `--black #1A1A1A` (cards), `--green #7D9B76` (accent/CTA), `--white`, `--grey #D8D8D8`. Type is Bebas Neue (headings, uppercase, letter-spaced) and Barlow Condensed (body, 400 and 700), self hosted: three latin subset `woff2` files in `/fonts`, declared by inline `@font-face` rules and two `preload` links repeated in every page's `<head>`. Nothing loads from Google Fonts. `vercel.json` caches `/fonts/*` for a year as immutable, so a changed font needs a new file name. Note `thank-you.html` uses stale variable *names* from an earlier red palette (`--red`, `--gold`) that are now assigned green values — don't "fix" the values to match the names.

## Page roles

- **Content pages** (`index`, `jiu-jitsu`, `boxing`, `muay-thai`, `mma`, `martial-arts`, `kids`, `homeschool`, `coaches`, `schedule`, `pricing`, `private-lessons`, `the-gym`, `competition-team`, `free-trial`) — full site chrome, in the sitemap. The main menu holds eleven links and its CSS is sized for exactly eleven; `mma`, `martial-arts` and `competition-team` are reached from the footer link row and from page copy, not the menu.
- **`mma.html`** — the MMA class: Tuesday and Thursday 7:30 PM, coached by Paulo Games, combining Jiu-Jitsu, wrestling, judo, kickboxing, Muay Thai and karate. The page states no level and no sparring rule because the owner has not supplied them; do not add either until he does.
- **`martial-arts.html`** — the hub for the term martial arts: every program with its class times and page, where to start, and the answer that karate, judo and wrestling are taught inside the MMA class. Class times here repeat `schedule.html`; change both together. The class options on `free-trial.html` and `go/jiu-jitsu.html` also carry each class's times in a `data-schedule` attribute (with a readable `data-label`); the forms send them as `class_label` and `class_schedule`, GoHighLevel saves them to the contact fields Class Interest and Class Schedule, and the first text to a new lead quotes them. A schedule change means editing those attributes too.
- **`404.html`** — Vercel serves it for any address that matches no file. `noindex, follow`, no canonical, no JSON-LD, not in the sitemap. Keep every asset path root relative, since it renders at any depth.
- **`lp.html`** — standalone Google Ads landing page. Deliberately minimal: no nav, no footer, no site CSS, system font stack for the body, a daily-resetting countdown, and a GoHighLevel form iframe. Not in the nav or sitemap. Optimized for load speed; keep it that way when editing.
- **`thank-you.html`** — post-conversion page, `noindex, nofollow`, and the only page carrying the Google Ads tag. Its "What Happens Next" copy deliberately promises no specific response time; if the gym commits to an SLA (e.g. "text within 15 minutes"), that's the line to change.
- **`privacy-policy.html`, `terms.html`** — legal, minimal chrome.
- **`googled018ab236e6d501f.html`** — Google Search Console verification. Leave alone.

## Routing

`vercel.json` sets `cleanUrls: true`, so all internal links use extensionless paths (`/boxing`, `/free-trial`). It also holds a temporary redirect from `/review` to the Google review form (for the front desk QR card), and permanent redirects for retired routes (`/camp`, `/kids-camp` → `/`) and canonicalization (`/index.html` → `/`, `/privacy-policy.html` → `/privacy-policy`). New pages need a sitemap entry; retired pages need a redirect here, not just a deletion.

On `index.html` the logo and Home link point at `#home` (the page has in-page anchor sections); on every other page they point at `/`.

## Lead capture and tracking

Three separate paths, all feeding GoHighLevel — don't assume one covers the others:

1. **`free-trial.html`** — hand-rolled form (`#dfc-booking-form`) that `POST`s JSON directly to a LeadConnector webhook. Kids options carry `data-youth="1"`: the top name fields relabel to the student's name, required parent first and last name fields and a student age field appear, and the payload sends the **parent** as `firstName`/`lastName` (GoHighLevel texts the contact by first name) with the child in `student_first_name`, `student_name` and `student_age`, plus `guardian_name`. Both forms also send `class_line`, the phrase GoHighLevel's first text quotes (contact field Class Line): the class label, plus " for <child's first name>" on kids leads. A kids option with `data-adult` (Kids Jiu-Jitsu, Youth Boxing) switches a student aged 15 or older to that adult class's label and times and adds ". Students 15 and older train in our adult classes"; the form shows a note saying so. Homeschool has no `data-adult` (all ages). Adult options send the typed name as before. Has a honeypot input `website_url_hp`, fires `gtag('event','generate_lead')` on success, and swaps the form for an inline confirmation (it does **not** redirect to `/thank-you`). On failure it alerts with the phone number.
2. **`lp.html`** — GoHighLevel form iframe (`form_embed.js`); redirect-to-thank-you is configured in GHL, not in this repo.
3. **Schedule/booking embeds** — Gymdesk `widgets.js` with gym id `6zgd3`, embedded on most content pages.

Analytics: GA4 `G-KYCVH9837V` in the `<head>` of every content page. Google Ads has two tags, for two different Ads accounts; do not merge them:

- `AW-18500089527` is the live Ads account (684 798 5141, the Search campaign started November 2026). Its `gtag('config', ...)` line sits right under the GA4 config on every content page and on `go/jiu-jitsu.html`, so the ad click is remembered on whichever page a visitor lands. Both hand-rolled forms (`free-trial.html` and `go/jiu-jitsu.html`) fire `gtag('event', 'conversion', { send_to: 'AW-18500089527/bn4ECKebxbsdELftw_VE' })` next to `generate_lead`, only after the webhook returns OK. That label belongs to the conversion action "Lead form sent". A new page with its own form needs both lines.
- `AW-18094262765` is an older Ads account and stays **only** on `thank-you.html`, for the `lp.html` flow.

Meta Pixel `1510598542567332` (the dataset "Facebook Pixel" in the Detroit Fight Company business portfolio) is live in the `<head>` of every page that carries the site chrome, plus `404.html`, `thank-you.html` and `go/jiu-jitsu.html`. It fires `PageView` on load. Both hand-rolled forms fire `fbq('track', 'Lead')` right after the Google Ads conversion, only after the webhook returns OK. No name, email, phone or form value is passed to it. The snippet is shared chrome: a new content page needs it, and a new form needs the Lead line. `lp.html`, `privacy-policy.html` and `terms.html` do not carry it.

Lead source: every content page and `go/jiu-jitsu.html` carry a short `<script>` right under the analytics block. Once per visit it saves where the visitor came from in `sessionStorage` under `dfc_lead_source`: a readable `lead_source` label (Yelp, Google Ads, Google Business Profile for `utm_source=google` with a `utm_medium` starting `gbp`, Google search, Direct, or the raw `utm_source` for a tag it does not know), the `utm_source`, `utm_medium` and `utm_campaign` values, the referring site, and the landing page. It keeps no click id and nothing personal; a `gclid` only sets the label to Google Ads. Both forms (`free-trial.html` and `go/jiu-jitsu.html`) read it through `leadSource()` and send those six fields in the webhook payload, next to the older `source`, `source_page` and `sourcePage` fields, which are unchanged because GoHighLevel may already map them. The snippet is shared chrome: a new content page needs it, and a new form needs the six fields. The fields show on a GoHighLevel contact only after the agency maps them in the workflow. Outside links that should be counted carry tags, for example the Yelp page button uses `?utm_source=yelp&utm_medium=page_button`.

## SEO surface

This site was built to be read by search engines and AI crawlers, and several files must stay in sync when content changes:

- `sitemap.xml` — manual list of the extensionless canonical URLs with `lastmod`.
- `robots.txt` — explicitly allows GPTBot, OAI-SearchBot, ChatGPT-User, ClaudeBot, Claude-Web, PerplexityBot, Google-Extended.
- `llms.txt` — plain-language summary of location, programs, pricing, and key URLs for LLM consumers.
- Per-page `<head>`: canonical, Open Graph, and Twitter card tags.
- Per-page inline JSON-LD: the business as `SportsActivityLocation` with `"@id": "https://detroitfight.com/#business"` on every content page (same type and same `telephone` format everywhere), plus `Service` + `BreadcrumbList` + `FAQPage` on program pages, `FAQPage` on `index`, `Person` on `coaches`. Every visible FAQ answer has a matching `FAQPage` entry; edit both.

## IndexNow (automatic, Bing side)

`.github/workflows/indexnow.yml` runs after every successful Vercel production deploy and submits the changed page URLs to IndexNow (Bing, which feeds ChatGPT and Copilot search) via `.github/scripts/indexnow.py`. The key file `<32 hex>.txt` at the repo root is the public IndexNow key; leave it alone, and keep `.vercelignore` excluding `.github`. Google ignores IndexNow and reads `sitemap.xml` on its own schedule, so sitemap `lastmod` still has to be bumped by hand for every changed page; Search Console "Request indexing" stays manual (Google offers no API for it).

## Business facts repeated across files

Changing any of these means grepping the whole repo, including `llms.txt`, JSON-LD blocks, and meta descriptions:

- Address: 1425 Tuskawilla Rd #209, Winter Springs, FL 32708
- Phone: (407) 696-6969 · Email: sean@detroitfight.com
- Text links: every `sms:` link and every "Text" label in the header points at (407) 955-5004, the gym's texting line inside GoHighLevel, where the front desk sees the conversation. (407) 696-6969 is the landline: `tel:` links only, never `sms:`. Body copy reads "Call 407-696-6969 or text 407-955-5004". The one exception is `private-lessons.html`, whose "Text Sean" buttons go to Sean's own cell and stay that way.
- Pricing: the $199/mo All Access Membership, no contracts, plus the Homeschool PE Program at $400/mo (Monday to Thursday 10:00 AM to 12:00 PM, starting January 11, 2027; Jiu-Jitsu only, no Boxing hour; open to all ages, 5 through high school; no published cap on class size; includes All Access; Enrollment Kit not included). On either plan, students 15 and older train in the adult Jiu-Jitsu and Boxing classes, not the kids classes. The free group PE day for homeschool groups is a separate thing: that one is a Jiu-Jitsu class and a Boxing class back to back. Both rates are also the gym's two Step Up EMA service offerings, so the site and EMA must match. Owner's rule: no free gi for scholarship students; the $150 Enrollment Kit applies to everyone.
- Offer: free trial class (the current site-wide CTA language)
- Visitors: dropping in on an adult Gi or No Gi Jiu-Jitsu class is $40. On the first Saturday of every month the 11:00 AM to 12:30 PM Jiu-Jitsu class is an open mat, free for everyone, all affiliations welcome (owner, November 21, 2026). Stated on `jiu-jitsu.html` (card and FAQ), `schedule.html` and `llms.txt`. Both `jiu-jitsu.html` and `schedule.html` carry an `Event` JSON-LD block for the next first Saturday; move its dates forward each month.
- Kids classes: Kids Jiu-Jitsu and Youth Boxing, ages 5 to 14. Owner's rule: the kids class is never labeled Gi or No Gi. Only the adult program is.
