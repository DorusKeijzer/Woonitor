Here live the crawlers, writers and scrapers. The crawler's role is to find urls for a given region and write these to a redis message queue. The scraper's role is to listen to the message queue and to visit the crawled urls and to write the info of the listing to another message queue. The writer in turn listens to the scraped data message queue and writes the data to the database. 

These services are orchestrated using [docker-compose](https://docs.docker.com/compose/), and work can (optionally) be distributed between multiple machines, you just need to choose which machine performs which task.

# Getting started
First clone this repo to every machine you are using, then determine which machine will host the message queue and database that the crawlers write to. For each of these services (database and message que) there should be 1 and no more than 1 machine (and these can be the same machine). If you have made your decision, create the `.env` files according to the instructions below. If you have just one machine at your disposal, use that as the message queue host.

## .env files

### On the database host
Create `.env` file according to `.env.template` and set `POSTGRES_HOST` to `localhost`. Make sure that the postgres port (default: 5432) is exposed to every other machine and your firewall does not block their access.

### On the message queue host 
Create `.env` file according to `.env.template` and set `REDIS_HOST` to `localhost`. Make sure that the redis port (default: 6379) is exposed to every other machine and your firewall does not block their access.

### On the non-database/message queue machines
Create `.env` file according to `.env.template` and set `REDIS_HOST` and `POSTGRES_HOST` to respectively the IP address of the message queue machine and the database host machine. 

## spinning up the services
You can spin up containers using the following commands, with profile flags in \[\]. Just make sure that:

- I the message queue host (and *only* the message queue host) uses the `--profile redis` flag (possibly in conjunction with the other profiles), 
- II *mutatis mutandis* for the database host 
- III every profile flag is used at least once. 

Now you can use the command like so:

```bash
docker compose [--profile message_queue] [--profile scraper] [--profile crawler] [--profile database] [--profile writer] up -d
```
For instance, on the redis and database host:

```bash
docker compose --profile message_queue --profile database --profile crawler up -d
```
and then on other machines:
```bash
docker compose --profile scraper --profile writer up -d
```

If you run all services on the same machine:

```bash
docker compose --profile redis --profile crawler --profile scraper --profile writer up -d
```
