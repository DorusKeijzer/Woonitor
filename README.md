# Woonitor

Woonitor scrapes sold Funda.nl listings, stores them in Postgres, visualises the
market in a Streamlit dashboard, and (work in progress, see [ROADMAP.md](ROADMAP.md))
models asking prices. It is a personal/portfolio project — see the "Status &
limitations" section below before trusting any number it produces.

```
crawler ──▶ redis queue ──▶ scraper ──▶ redis queue ──▶ writer ──▶ postgres
                                                                     │
                              ┌──────────────────────────────────────┤
                     streamlit dashboard                    machine_learning/
prometheus + pushgateway + grafana + exporters observe all of the above
```

- **crawler** — given an area (e.g. "Tilburg"), pages through Funda's search
  results for that area and pushes listing URLs onto a Redis queue, deduping
  against a Redis set.
- **scraper** — listens on that queue, visits each listing with Playwright, and
  pushes the scraped fields onto a second Redis queue.
- **writer** — listens on the scraped-data queue, validates and transforms each
  message into the `listings` schema, and batch-inserts into Postgres
  (`ON CONFLICT (funda_id) DO NOTHING`).
- **dashboard** (`dashboard/app.py`) — Streamlit app with price/time-on-market
  trends, a neighbourhood choropleth, and energy-label breakdowns.
- **machine_learning/** — asking-price modelling; currently a research script,
  see the roadmap for the plan to turn it into a proper pipeline + API.
- **monitoring** — each service pushes metrics to a Prometheus Pushgateway;
  Prometheus scrapes it plus Postgres/Redis exporters, Grafana visualises it.

These services are orchestrated using [docker-compose](https://docs.docker.com/compose/), and work can (optionally) be distributed between multiple machines, you just need to choose which machine performs which task.

## Status & limitations

- Funda only exposes **asking price**, not the actual sale price — every price
  figure in this project is an asking price.
- Only *sold* listings are scraped (`availability=unavailable`), which is a
  selection bias for any time-on-market analysis.
- Funda caps search results at ~9990 listings per query, so no city's history is
  ever fully captured.
- This is a personal project scraping a third party's website; it's built for
  learning/portfolio purposes, not resale or high-volume use.
- See [ROADMAP.md](ROADMAP.md) for the full list of known gaps and the plan to
  address them.

# Getting started
First clone this repo to every machine you are using, then determine which machine will host the backend (message queue, database, monitoring) that the crawlers write to. this should be 1 and no more than 1 machine. If you have made your decision, create the `.env` files according to the instructions below. If you have just one machine at your disposal, use that machine for everything.

## .env files

### On the backend host
Create `.env` file according to `.env.template` and set `REDIS_HOST`, `POSTGRES_HOST` and `PUSHGATEWAY_URL` to respectively `redis` and `postgres` and `http://pushgateway:9091`. Make sure that the redis, postgres and pushgateway ports (defaults: 5432, 6379 and 9091) are exposed to every other machine and your firewall does not block their access.

### On the other machines
Create `.env` file according to `.env.template` and set `REDIS_HOST` and `POSTGRES_HOST` to respectively the IP address of the backend host machine. `PUSHGATEWAY_URL` should be: `http:[backend host IP]:9091`

## spinning up the services
You can spin up containers using the following commands, with profile flags in \[\]. Just make sure that:

- I the message queue host (and *only* the message queue host) uses the `--profile backend` flag (possibly in conjunction with the other profiles), 
- II every profile flag is used at least once (i.e.: you have at least one backend, scraper, writer and crawler)

Now you can use the command like so:

```bash
docker compose [--profile backend] [--profile scraper] [--profile crawler] [--profile writer] up -d
```
For instance, on the backend host:

```bash
docker compose --profile backend --profile crawler up -d
```
and then on other machines:
```bash
docker compose --profile scraper --profile writer up -d
```

If you run all services on the same machine:

```bash
docker compose --profile backend --profile crawler --profile scraper --profile writer up -d
```
