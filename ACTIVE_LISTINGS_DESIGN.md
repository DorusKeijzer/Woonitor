# Active Listings: Design Sketch

Status: **design only, not implemented.** Captured here so the idea isn't lost
before we build it. See [ROADMAP.md](ROADMAP.md) for how this fits into the
broader plan (it's the prerequisite for the "good deal" flagger and the
time-to-sell survival model discussed there).

## The problem

Right now the crawler only takes `availability=["unavailable"]` (sold)
listings. To build anything that helps a live house-hunter ("is this a good
deal", "how fast will this sell"), we need to track *currently for-sale*
listings too — which means periodically checking hundreds/thousands of active
listings for changes (price cuts, withdrawal, sale) without re-scraping every
single one's full detail page every single crawl pass. That would be wasteful
and disrespectful of Funda's servers for very little benefit, since most
listings don't change between crawls.

## The design: hash-based change detection

1. **Crawler gets an `available` mode** alongside the existing `unavailable`
   one. Walking the search-result pages, it grabs not just the `/detail/`
   link (like today) but the **card-level summary** too — price, address,
   m², rooms, whatever's actually rendered on the card without a detail-page
   visit. (Not yet verified what's really on the card — needs the same kind
   of live-page selector inspection done for the Kenmerken features fix.)

2. **Hash that summary per listing** and compare against the last-seen hash,
   kept in Redis — same lightweight pattern as the existing `listing_seen`
   set (e.g. a Redis hash `funda_id → summary_hash`).

3. **Only enqueue a full detail-page scrape** (the expensive Playwright
   visit) when:
   - it's a brand-new active listing (never seen before), or
   - its summary hash changed since last check (price cut, etc.)

   Unchanged listings are skipped entirely — no detail-page hit at all. This
   is the actual cost saving: the aggregation-page crawl stays cheap and can
   run frequently; only new/changed listings hit the expensive path.

4. **Disappearance matters too.** A listing tracked last pass but missing
   this pass either sold or was withdrawn. Worth one final detail-page visit
   to find out which — that's the actual "did this house sell, and when"
   signal the time-to-sell model needs.

## Why to log price changes, not just overwrite them

When the hash changes because of a price cut, don't just overwrite the stored
price — **log it** to a small `price_history` table:

```
price_history(funda_id, price, observed_at)
```

This captures the full asking-price trail over a listing's life (every cut,
every date). It's genuinely the one piece of data that doesn't exist anywhere
else — Kadaster (the land registry) only has the final sale price, never the
negotiation/pricing-strategy trail. This is the "listing process" data
flagged in the business-viability discussion as the one narrow thing this
project has that official/incumbent data sources don't.

## Schema approach

Extend the existing `listings` table rather than maintaining a parallel one:

- Add a `status` column (`active` / `sold` / `withdrawn`)
- Make `sell_date` and `sell_duration` nullable (an active listing doesn't
  have these yet)
- Add the new `price_history` table above

One table serves both training data (`WHERE status = 'sold'`) and live
scoring (`WHERE status = 'active'`) instead of two schemas drifting apart
over time.

## Work items, roughly in build order

1. Live inspection of a real search-results page to find the card-summary
   selectors (price/address/m²/rooms on the card itself)
2. Schema migration: `status` column, nullable sell fields, new
   `price_history` table
3. Crawler: `available` mode, hash-diff logic against the Redis fingerprint
   cache, "disappeared listing" tracking pass
4. Writer: `validate_output` needs to stop requiring sell-specific fields
   when `status = 'active'`
5. Decide re-crawl cadence for the `available` aggregation pages (daily is
   probably plenty — no need for real-time freshness)
