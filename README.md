# Ariadne

Ariadne is a personal information-flow processing system. It collects RSS and internet items, deduplicates them, analyzes them, pushes useful results to Feishu, records feedback, and exports selected knowledge into Obsidian.

## First Milestone

The current implementation is a local-first skeleton:

- FreshRSS for source aggregation.
- Postgres for durable state.
- FastAPI for health checks, job creation, and Feishu feedback callbacks.
- A Python worker backed by a Postgres `jobs` table.
- Dry-run Feishu push when no webhook is configured.
- Obsidian Markdown export when `OBSIDIAN_VAULT_PATH` is configured.

Redis and Celery are intentionally not part of the first version.

## Local Setup

1. Optionally copy `.env.example` to `.env`.
2. Optionally set `RSS_FEED_URLS` to one or more comma-separated RSS or Atom feed URLs.
3. Optionally set `FRESHRSS_FEED_URLS` to one or more FreshRSS output feed URLs.
4. Start the stack:

```bash
docker compose up --build
```

Useful endpoints:

- `GET http://localhost:8000/health`
- `POST http://localhost:8000/internal/jobs` with `{"type":"ingest","payload":{}}`
- `POST http://localhost:8000/internal/jobs` with `{"type":"ingest","payload":{"sample":true}}`
- `POST http://localhost:8000/internal/jobs` with `{"type":"ingest","payload":{"feed_urls":["https://hnrss.org/frontpage"]}}`
- `POST http://localhost:8000/internal/jobs` with `{"type":"push_digest","payload":{"limit":10,"force":true}}`
- `POST http://localhost:8000/feishu/events` with `{"item_id":"...","action":"save_obsidian"}`

FreshRSS is exposed directly at `http://localhost:8080` and through Nginx at
`http://localhost/freshrss/`.

Feishu push message structure is documented in `docs/feishu-message.md`.

By default, high-importance items are pushed immediately. Medium-importance
items wait for digest delivery at `DIGEST_SCHEDULE_TIMES`, which defaults to
09:00 and 17:00 in `Asia/Shanghai`.

Ingestion defaults to processing only the newest 100 entries per feed and only
entries published within the last 7 days. Entries without a published time are
kept.

## FreshRSS Feed Integration

FreshRSS is the RSS source management UI. Ariadne reads FreshRSS output feeds through the same ingestion pipeline used for normal RSS URLs.

Start FreshRSS and Nginx, then check their status:

```powershell
docker compose up -d freshrss nginx
docker compose ps freshrss nginx
```

Then open:

```text
http://localhost:8080
http://localhost/freshrss/
```

Use the FreshRSS page to initialize the user, add RSS sources, import OPML, group feeds, and check whether each source refreshes correctly.

Recommended first source for testing:

```text
https://hnrss.org/frontpage
```

After FreshRSS has articles, copy a FreshRSS output feed URL from the page. Configure Ariadne with:

```env
FRESHRSS_FEED_URLS=http://localhost:8080/path/to/freshrss/output
```

For Docker-to-Docker access, use the Compose service name instead of `localhost`:

```env
FRESHRSS_FEED_URLS=http://freshrss/path/to/freshrss/output
```

Or test a FreshRSS output URL as a one-shot job from the host:

```powershell
Invoke-RestMethod -Method Post http://localhost:8000/internal/jobs `
  -ContentType 'application/json' `
  -Body '{"type":"ingest","payload":{"feed_urls":["http://localhost:8080/path/to/freshrss/output"]}}'
```

FreshRSS remains responsible for source management. Ariadne remains responsible for deduplication, analysis, push, feedback, and Obsidian export.

If FreshRSS does not open, inspect logs:

```powershell
docker compose logs freshrss
docker compose logs nginx
```

Run a database smoke check against the local Compose database:

```bash
python -m ariadne.smoke
```

The local default database URL uses `127.0.0.1` instead of `localhost` to avoid slow IPv6 resolution on some Windows setups.

Run a deterministic local sample through the pipeline:

```powershell
Invoke-RestMethod -Method Post http://localhost:8000/internal/jobs `
  -ContentType 'application/json' `
  -Body '{"type":"ingest","payload":{"sample":true}}'
```

The sample item is deterministic. Re-running it should not create duplicate normalized items, analysis rows, or dry-run push events.

Ad-hoc `feed_urls` jobs run once by default. Add `"repeat": true` to the payload if the worker should schedule the same feed again.

Ad-hoc ingestion can override the default guardrails:

```powershell
Invoke-RestMethod -Method Post http://localhost:8000/internal/jobs `
  -ContentType 'application/json' `
  -Body '{"type":"ingest","payload":{"feed_urls":["https://hnrss.org/frontpage"],"max_item_age_days":3,"max_items_per_feed":30}}'
```
