# Woonitor — Roadmap

Woonitor is a distributed pipeline that scrapes sold Funda listings, stores them in
Postgres, visualises the market in a Streamlit dashboard, and models asking prices.
It runs on a single rented Strato server via `docker compose` profiles, but is
designed so crawling/scraping/writing can be split across machines.

```
crawler ──▶ redis queue ──▶ scraper ──▶ redis queue ──▶ writer ──▶ postgres
                                                                     │
                              ┌──────────────────────────────────────┤
                     streamlit dashboard                    machine_learning/
prometheus + pushgateway + grafana + exporters wrap everything
```

This document tracks the work needed to take it from "working prototype with holes"
to a portfolio piece for junior data science / software engineering / MLE roles.

---

## Current state (2026-09-11)

**Update:** everything in the "Broken / weak" table below tagged crawler/scraper/
writer/project-hygiene has been fixed as of Phase 0/1 (see checklists below for
specifics). The `ml`/`serving` rows are still open — that's Phase 2/3.

### Works
- Compose profile design and the multi-host split.
- `writer.py`: `validate_input → transform → validate_output`, batched inserts,
  `ON CONFLICT DO NOTHING` dedup, pure Dutch date/room/postcode parsers.
- Crawler Redis Lua dedup script (atomic seen-set + queue push).
- Monitoring stack is fully wired (pushgateway, postgres/redis exporters, scrape config).
- Dashboard renders ~10 Plotly charts plus a GeoJSON choropleth.
- `.env` never committed; venvs not tracked; `.gitignore` is sane.

### Broken / weak
| Area | Issue |
| --- | --- |
| crawler | `base_url` hardcoded to all-cities, ignores `area` arg; payload still tags URLs with `cleaned_area` → listings mislabelled |
| crawler | `cur.execute(... WHERE url = %s, (urls,))` passes the whole list, not the single url |
| crawler | opens a Postgres connection it does not need (dedup already covered by Lua set + writer `ON CONFLICT`) |
| crawler | 403/429 handling commented out — no backoff |
| crawler | Prometheus `job=self.name` carries a per-process UUID → pushgateway cardinality blowup |
| scraper | `listen()` has no error handling — one bad page kills the worker |
| scraper | captcha / "Storing" pages are detected but flow through and can become junk rows |
| scraper | leftover debug (`print(type(title))`), `headless=False` + Xvfb, slow per-listing browser |
| writer | `Counter('writer_writes', ..., ["writes"])` but every call is `.labels(code=...)` → raises on every write |
| writer | `executemany` uses `listings[0].keys()`; rows with different keys break the batch |
| writer | `split_postcode_city("1234 AB Den Haag")` → city becomes `"Den"`; Den Haag corrupted everywhere downstream |
| writer | Alembic is a dependency but schema is raw `init/*.sql` |
| ml | `predict_price.py` calls `plt.show()` in a loop — cannot run in its own container (`ml.dockerfile` runs exactly this) |
| ml | `detrend()` runs on the full dataframe before the split → leakage via trend/neighbour info |
| ml | `pd.read_sql` with a psycopg3 connection (needs SQLAlchemy) |
| ml | no baseline, no model persistence, no saved metrics; per-quantile `R2`; unsmoothed target encoding; dead `return` lines |
| ml | trains on sold-only listings under a 9990-result Funda cap — selection bias, unmentioned |
| serving | `machine_learning/api.py` is just `import fastapi`; `cluster_neighborhoods.py` is empty |
| project | zero tests, no CI, no linting |
| project | README covers only the scrapers |
| project | Grafana has a datasource but no dashboards — nothing visible on first boot |
| project | `catboost_info/` untracked and not ignored |
| project | README tells the reader to expose Postgres/Redis to the internet and open the firewall |

### Guiding principle
Range is already demonstrated. A smaller project that fully works beats a sprawling
one with holes. Fix correctness first, then make **one** pillar excellent — the
ML → API path, since it targets DS/MLE.

---

## Phase 0 — Hygiene (~0.5 day)

- [x] Add `catboost_info/` to `.gitignore` (`__pycache__/`/`*.py[codz]` were
      already covered).
- [x] Remove `api.py` and `cluster_neighborhoods.py` — both were empty/dead and
      unreferenced by any compose service. (`ml_services` runs
      `predict_price.py`, not `api.py`, so it was left as-is; it gets rebuilt
      properly in Phase 2/3.)
- [x] Removed `todo.md`; its remaining items live in "Stretch / later" below.
- [x] Partial `README.md` rewrite: mermaid architecture diagram, per-component
      description, honest "status & limitations" section (asking-price-only,
      sold-only selection bias, 9990-result cap, personal-project disclaimer).
- [ ] One-command local run instructions, screenshots — deferred to Phase 5
      (needs a live/seeded instance to capture from).
- [ ] GitHub issues for the roadmap items — not done, tracking here for now.
- [ ] Funda ToS / CBS-Kadaster note — captured only briefly; expand in Phase 5.

## Phase 1 — Make the pipeline correct (~2–3 days)

- [x] Fixed `split_postcode_city` for multi-word cities (`"2511 CV Den Haag"` →
      `"Den Haag"`, not `"Den"`). **Note:** this is a forward fix only — rows
      already written with `city = 'Den'` are not backfilled; that's a
      one-off `UPDATE`, deliberately not run automatically against the live DB.
- [x] Fixed the `writer_writes` Counter label bug (labelname is now `status`,
      matching a live hotfix that was already applied directly on the server
      but never committed — see below).
- [x] Fixed `write()` to union columns across the batch instead of assuming
      every listing has the same keys as `listings[0]`.
- [x] Crawler:
  - [x] honour the `area` argument (was hardcoded to an all-cities query)
  - [x] removed the buggy/redundant Postgres dedup check entirely — dedup is
        the Lua script's Redis set + the writer's `ON CONFLICT`
  - [x] exponential backoff on 403/429 (retries the same page, gives up after
        `CRAWLER_MAX_CONSECUTIVE_BLOCKS`)
  - [x] stable Prometheus `job="crawler"` label + `grouping_key={"instance": ...}`
        (also applied the same fix to scraper and writer — same cardinality bug)
- [x] Scraper:
  - [x] wrapped `listen()` in try/except with a `listing_queue_dead` dead-letter list
  - [x] captcha / "Storing" pages now requeue the URL instead of writing a
        near-empty row to `data_queue`
  - [x] removed debug prints
- [x] Hardened `validate_input` to also require `"Titel"` (defense-in-depth
      against blocked pages slipping through)
- [x] `PLAYWRIGHT_HEADLESS` env flag (default `true`, drops the hard requirement
      on Xvfb) — kept configurable rather than hardcoded since Funda's anti-bot
      may fingerprint headless Chromium harder; documented in `.env.template`.
- [ ] Alembic migration for `init/01_create_schema.sql` — **deliberately
      skipped**. The deployed Postgres volume already has 13 months of scraped
      data on the current schema; introducing Alembic mid-flight needs a
      baseline migration stamped against that live DB, which is a distinct,
      riskier piece of work best done deliberately, not folded into a hygiene pass.

### Found during deployment: uncommitted server-side hotfixes

`strato_II:/root/Woonitor` had uncommitted local edits never pushed upstream.
Most were an early draft already superseded by later commits on `main`
(dashboard rewrite, dockerfile tweaks, a plotly version bump). Two were real
fixes folded into this pass:
- `writer.py`: the same `writer_writes` Counter label fix (they used label name
  `status`, adopted here for consistency).
- `docker-compose.yml`: `streamlit`'s `depends_on` pointed at the container_name
  `postgres_db` instead of the service name `postgres` — already fixed on
  `main`. `postgres` was also missing from the `ml` profile list — added here so
  `--profile ml` brings up its own DB dependency.

## Phase 2 — Turn the ML script into a project (~3–4 days) — headline

- [ ] Split `machine_learning/` into `data.py` / `features.py` / `train.py` /
      `evaluate.py` / `predict.py`.
- [ ] Temporal train/val/test split (no random split on a time series).
- [ ] Fix leakage: compute trend on the training window only; K-fold target
      encoding with smoothing.
- [ ] Baseline model (median €/m² by city + neighbourhood) and report lift over it.
- [ ] One justified model (CatBoost with native categorical support; drop the manual
      one-hot + KMeans). Keep quantile models only for the prediction-interval plot.
- [ ] Persist the model; write `reports/metrics.json`; save plots to files (no
      `plt.show()`); use a SQLAlchemy engine for `read_sql`.
- [ ] `MODEL_CARD.md`: data, features, metrics, limitations (drift, sold-only
      selection bias, scrape cap).
- [ ] `notebooks/eda.ipynb` for the exploration narrative.

## Phase 3 — Serving (~2 days) — MLE story

- [ ] Real `api.py`: FastAPI with `/health` and `/predict` (Pydantic request model,
      loads the persisted model, returns point estimate + interval).
- [ ] Add it to compose as a proper service with a port; `ml.dockerfile` CMD →
      `uvicorn`, training as a separate one-off/cron entrypoint.
- [ ] "Predict a price" page in the Streamlit dashboard that calls the API.

## Phase 4 — Tests & CI (~2 days) — SWE credibility

- [ ] pytest: unit tests for `writer.transform` and the parsers, feature
      engineering, and the API via `TestClient`; a fakeredis test for the queue flow.
- [ ] GitHub Actions: ruff + black + pytest + `docker build`.
- [ ] `.pre-commit-config.yaml`.

## Phase 5 — Portfolio polish (~1–2 days)

- [ ] Commit a small sanitised seed dataset so `docker compose up` gives a working
      dashboard + API without scraping.
- [ ] Provision a Grafana dashboard JSON (throughput, error rates, queue depth).
- [ ] Screenshots / short GIF in the README.
- [ ] Remove the "open your firewall" instructions; note Postgres/Redis stay private
      and Grafana/Streamlit sit behind a reverse proxy with auth.

---

## Stretch / later

- Time-to-sell model (`todo.md` DS #2).
- Anomaly detection: probabilistic regression to flag outlier listings.
- Price explanation (SHAP) surfaced in the dashboard.
- Automatic daily rescraping with per-city backoff and a queue template.
- Map tile caching in the dashboard.
- Supplement/replace Funda with CBS open data so the project does not rot when the
  scrapers break.
