Here live the crawlers and scrapers. The crawler's role is to find urls for a given region, the scraper's role is the visit those crawled urls and to return the info of the listing. These are orchestrated using [docker-compose](https://docs.docker.com/compose/), and work can (optionally) be distributed between multiple machines, you just need to choose which machine performs which task.

# Getting started
First clone this repo to every machine you are using, then determine which machine will host the message queue that the crawlers write to and create `.env` files according to the instructions below. If you have just one machine at your disposal, use that as the message queue host.

## .env files

### On the message queue host 
Create `.env` file according to `.env.template` and set `REDIS_HOST` to `localhost`. Make sure that the redis port (default: 6379) is exposed to every other machine and your firewall does not block their access.

### On the other machines
Create `.env` file according to `.env.template` and set `REDIS_HOST` to the IP address of the message queue machine. 

## spinning up crawlers/scrapers/redis containers
You can spinn up containers using the following command, with optionnal flags in \[\]. Just make sure that the message queue host (and *only* the message queue host) uses the `--profile redis` flag (possibly in conjunction with the other profiles). 

```bash
docker compose [--profile redis] [--profile scraper] [--profile crawler] up -d
```
For instance, on the redis host:

```bash
docker compose --profile redis --profile crawler up -d
```
and then on other machines:
```bash
docker compose --profile scraper up -d
```

If you run all services on the same machine:

```bash
docker compose --profile redis --profile crawler --profile scraper up -d
```
