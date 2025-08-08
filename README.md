Here live the crawlers, writers and scrapers. The crawler's role is to find urls for a given region and write these to a redis message queue. The scraper's role is to listen to the message queue and to visit the crawled urls and to write the info of the listing to another message queue. The writer in turn listens to the scraped data message queue and writes the data to the database. 

These services are orchestrated using [docker-compose](https://docs.docker.com/compose/), and work can (optionally) be distributed between multiple machines, you just need to choose which machine performs which task.

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
