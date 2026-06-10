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

1. Copy `.env.example` to `.env`.
2. Set `RSS_FEED_URLS` to one or more comma-separated RSS or Atom feed URLs.
3. Start the stack:

```bash
docker compose up --build
```

Useful endpoints:

- `GET http://localhost:8000/health`
- `POST http://localhost:8000/internal/jobs` with `{"type":"ingest","payload":{}}`
- `POST http://localhost:8000/feishu/events` with `{"item_id":"...","action":"save_obsidian"}`

FreshRSS is exposed at `http://localhost:8080`.
