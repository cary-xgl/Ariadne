from __future__ import annotations

import json
import logging
import re
import time
import urllib.request
from datetime import datetime
from pathlib import Path

from ariadne.analysis import analyze_item
from ariadne.config import get_settings
from ariadne.db import connect
from ariadne.jobs import Job, claim_next, complete, enqueue, fail
from ariadne.rss import FeedItem, fetch_feed
from ariadne.sample import sample_feed_items
from ariadne.text import canonicalize_url, html_to_text, normalize_text, sha256_text, slugify, truncate_text

logger = logging.getLogger(__name__)
COMMENTS_URL_RE = re.compile(r"\bComments? URL:\s*(https?://\S+)", re.IGNORECASE)


def run_forever() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = get_settings()
    while True:
        processed = run_once()
        if processed == 0:
            time.sleep(settings.worker_poll_seconds)


def run_once() -> int:
    settings = get_settings()
    processed = 0
    with connect() as conn:
        for _ in range(settings.worker_batch_size):
            job = claim_next(conn)
            if job is None:
                break
            try:
                dispatch(conn, job)
                complete(conn, job.id)
                processed += 1
            except Exception as exc:
                logger.exception("Job failed: %s", job.id)
                fail(conn, job, exc)
    return processed


def dispatch(conn, job: Job) -> None:
    handlers = {
        "ingest": ingest,
        "normalize": normalize,
        "dedupe": dedupe,
        "analyze": analyze,
        "push": push,
        "push_digest": push_digest,
        "export_obsidian": export_obsidian,
    }
    handler = handlers.get(job.type)
    if handler is None:
        raise ValueError(f"Unknown job type: {job.type}")
    handler(conn, job.payload)


def ingest(conn, payload: dict) -> None:
    if payload.get("sample"):
        for item in sample_feed_items():
            raw_item_id = upsert_raw_item(conn, item)
            enqueue(conn, "normalize", {"raw_item_id": raw_item_id})
        return

    settings = get_settings()
    feed_urls = payload.get("feed_urls") or settings.feed_urls
    if not feed_urls:
        logger.info("No RSS_FEED_URLS configured; ingestion skipped.")
        return

    for feed_url in feed_urls:
        for item in fetch_feed(feed_url):
            raw_item_id = upsert_raw_item(conn, item)
            enqueue(conn, "normalize", {"raw_item_id": raw_item_id})

    if _should_reschedule_ingest(payload):
        enqueue(conn, "ingest", {"feed_urls": feed_urls, "repeat": True}, run_after_seconds=900)


def _should_reschedule_ingest(payload: dict) -> bool:
    if "repeat" in payload:
        return bool(payload["repeat"])
    return "feed_urls" not in payload


def upsert_raw_item(conn, item: FeedItem) -> str:
    source = conn.execute(
        """
        INSERT INTO sources (type, name, url)
        VALUES ('rss', %s, %s)
        ON CONFLICT (url) DO UPDATE SET name = EXCLUDED.name, updated_at = now()
        RETURNING id
        """,
        (item.source_name, item.source_url),
    ).fetchone()
    row = conn.execute(
        """
        INSERT INTO raw_items (
          source_id, external_id, url, title, author, published_at, raw_content, raw_payload, content_hash
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
        ON CONFLICT (source_id, external_id) DO UPDATE SET
          title = EXCLUDED.title,
          raw_content = EXCLUDED.raw_content,
          raw_payload = EXCLUDED.raw_payload,
          content_hash = EXCLUDED.content_hash
        RETURNING id
        """,
        (
            source["id"],
            item.external_id,
            item.url,
            item.title,
            item.author,
            item.published_at,
            item.content,
            json.dumps(item.raw_payload),
            item.content_hash,
        ),
    ).fetchone()
    return str(row["id"])


def normalize(conn, payload: dict) -> None:
    raw_item_id = payload["raw_item_id"]
    raw_item = conn.execute("SELECT * FROM raw_items WHERE id = %s", (raw_item_id,)).fetchone()
    if raw_item is None:
        raise ValueError(f"raw_item not found: {raw_item_id}")

    canonical_url = canonicalize_url(raw_item["url"])
    content = normalize_text(raw_item["raw_content"])
    normalized_hash = sha256_text(f"{raw_item['title']}\n{canonical_url}\n{content}")
    existing = conn.execute(
        "SELECT id FROM items WHERE canonical_url = %s",
        (canonical_url,),
    ).fetchone()
    if existing is not None:
        logger.info("Item already normalized; skipping duplicate raw item: %s", raw_item_id)
        return

    row = conn.execute(
        """
        INSERT INTO items (raw_item_id, canonical_url, title, content, normalized_hash)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
        """,
        (raw_item_id, canonical_url, raw_item["title"], content, normalized_hash),
    ).fetchone()
    enqueue(conn, "dedupe", {"item_id": str(row["id"])})


def dedupe(conn, payload: dict) -> None:
    item_id = payload["item_id"]
    item = conn.execute("SELECT * FROM items WHERE id = %s", (item_id,)).fetchone()
    if item is None:
        raise ValueError(f"item not found: {item_id}")
    if item["dedupe_group_id"] is not None:
        logger.info("Item already deduplicated; skipping: %s", item_id)
        return

    duplicate = conn.execute(
        """
        SELECT id, dedupe_group_id
        FROM items
        WHERE id <> %s
          AND (canonical_url = %s OR normalized_hash = %s)
        ORDER BY created_at
        LIMIT 1
        """,
        (item_id, item["canonical_url"], item["normalized_hash"]),
    ).fetchone()

    if duplicate is None:
        group = conn.execute(
            """
            INSERT INTO dedupe_groups (representative_item_id, reason)
            VALUES (%s, 'canonical_url')
            RETURNING id
            """,
            (item_id,),
        ).fetchone()
        conn.execute("UPDATE items SET dedupe_group_id = %s, updated_at = now() WHERE id = %s", (group["id"], item_id))
        enqueue(conn, "analyze", {"item_id": item_id})
        return

    group_id = duplicate["dedupe_group_id"]
    if group_id is None:
        group = conn.execute(
            """
            INSERT INTO dedupe_groups (representative_item_id, reason)
            VALUES (%s, 'canonical_url')
            RETURNING id
            """,
            (duplicate["id"],),
        ).fetchone()
        group_id = group["id"]
        conn.execute("UPDATE items SET dedupe_group_id = %s, updated_at = now() WHERE id = %s", (group_id, duplicate["id"]))

    conn.execute(
        "UPDATE items SET dedupe_group_id = %s, status = 'ignored', updated_at = now() WHERE id = %s",
        (group_id, item_id),
    )


def analyze(conn, payload: dict) -> None:
    item_id = payload["item_id"]
    item = conn.execute("SELECT * FROM items WHERE id = %s", (item_id,)).fetchone()
    if item is None:
        raise ValueError(f"item not found: {item_id}")
    if item["status"] in {"pushed", "archived", "ignored"}:
        logger.info("Item already past analysis stage; skipping: %s", item_id)
        return
    if _analysis_exists(conn, item_id):
        logger.info("Analysis already exists; skipping: %s", item_id)
        if not _successful_push_exists(conn, item_id):
            enqueue(conn, "push", {"item_id": item_id})
        return

    conn.execute("UPDATE items SET status = 'analyzing', updated_at = now() WHERE id = %s", (item_id,))
    result = analyze_item(item["title"], item["content"])
    conn.execute(
        """
        INSERT INTO analysis_results (
          item_id, model_name, summary, topics, tags, importance_score, novelty_score,
          recommended_action, reason, raw_output
        )
        VALUES (%s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s, %s, %s::jsonb)
        """,
        (
            item_id,
            result.model_name,
            result.summary,
            json.dumps(result.topics),
            json.dumps(result.tags),
            result.importance_score,
            result.novelty_score,
            result.recommended_action,
            result.reason,
            json.dumps(result.raw_output),
        ),
    )
    conn.execute(
        "UPDATE items SET status = 'ready', summary = %s, updated_at = now() WHERE id = %s",
        (result.summary, item_id),
    )
    enqueue(conn, "push", {"item_id": item_id})


def push(conn, payload: dict) -> None:
    item_id = payload["item_id"]
    if _should_skip_push(conn, item_id, payload):
        logger.info("Successful push already exists; skipping: %s", item_id)
        return

    item = conn.execute(
        """
        SELECT i.*, s.name AS source_name, ar.reason, ar.importance_score
        FROM items i
        JOIN raw_items r ON r.id = i.raw_item_id
        JOIN sources s ON s.id = r.source_id
        LEFT JOIN LATERAL (
          SELECT reason, importance_score
          FROM analysis_results
          WHERE item_id = i.id
          ORDER BY created_at DESC
          LIMIT 1
        ) ar ON true
        WHERE i.id = %s
        """,
        (item_id,),
    ).fetchone()
    if item is None:
        raise ValueError(f"item not found: {item_id}")

    settings = get_settings()
    message = _format_push_message(item)
    message_id = "dry-run"
    status = "sent"
    error = None

    if settings.feishu_webhook_url:
        try:
            request = urllib.request.Request(
                settings.feishu_webhook_url,
                data=json.dumps(message).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=20) as response:
                message_id = response.read().decode("utf-8")[:500]
        except Exception as exc:
            status = "failed"
            error = str(exc)

    conn.execute(
        """
        INSERT INTO push_events (item_id, recipient, message_id, status, sent_at, last_error)
        VALUES (%s, %s, %s, %s, now(), %s)
        """,
        (item_id, settings.dry_run_push_recipient, message_id, status, error),
    )
    if status == "failed":
        raise RuntimeError(error)
    conn.execute("UPDATE items SET status = 'pushed', updated_at = now() WHERE id = %s", (item_id,))


def push_digest(conn, payload: dict) -> None:
    limit = _digest_limit(payload.get("limit", 10))
    force = bool(payload.get("force"))
    settings = get_settings()
    recipient = _digest_recipient()
    items = _fetch_digest_items(conn, limit, recipient, force)
    if not items:
        logger.info("No items available for digest push.")
        return

    message = _format_digest_message(items)
    message_id = "dry-run:digest"
    status = "sent"
    error = None

    if settings.feishu_webhook_url:
        try:
            request = urllib.request.Request(
                settings.feishu_webhook_url,
                data=json.dumps(message).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=20) as response:
                message_id = response.read().decode("utf-8")[:500]
        except Exception as exc:
            status = "failed"
            error = str(exc)

    for item in items:
        conn.execute(
            """
            INSERT INTO push_events (item_id, recipient, message_id, status, sent_at, last_error)
            VALUES (%s, %s, %s, %s, now(), %s)
            """,
            (item["id"], recipient, message_id, status, error),
        )
    if status == "failed":
        raise RuntimeError(error)


def _format_push_message(item: dict) -> dict:
    title = truncate_text(item["title"], 80)
    summary = truncate_text(_card_text_without_urls(item["summary"] or ""), 420)
    reason = truncate_text(_card_text_without_urls(item["reason"] or "No analysis reason"), 240)
    source = truncate_text(str(item.get("source_name") or "Unknown source"), 80)
    importance = item.get("importance_score")
    importance_text = f"{float(importance):.2f}" if importance is not None else "N/A"
    actions = [
        {
            "tag": "button",
            "text": {"tag": "plain_text", "content": "阅读全文"},
            "type": "primary",
            "url": item["canonical_url"],
        }
    ]
    comments_url = _extract_comments_url(item.get("summary"), item.get("reason"))
    if comments_url and comments_url != item["canonical_url"]:
        actions.append(
            {
                "tag": "button",
                "text": {"tag": "plain_text", "content": "讨论"},
                "type": "default",
                "url": comments_url,
            }
        )
    return {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "template": _card_template(importance),
                "title": {"tag": "plain_text", "content": title},
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": f"**摘要**\n{summary or 'No summary available.'}"},
                },
                {
                    "tag": "div",
                    "fields": [
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**来源**\n{source}"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**重要性**\n{importance_text}"}},
                    ],
                },
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": f"**推荐理由**\n{reason}"},
                },
                {
                    "tag": "action",
                    "actions": actions,
                },
            ],
        },
    }


def _format_digest_message(items: list[dict]) -> dict:
    elements = [
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**本次收录 {len(items)} 篇**\n按入库时间从新到旧排列。",
            },
        }
    ]
    for index, item in enumerate(items, start=1):
        title = truncate_text(item["title"], 90)
        summary = truncate_text(_card_text_without_urls(item["summary"] or ""), 180)
        source = truncate_text(str(item.get("source_name") or "Unknown source"), 50)
        importance = item.get("importance_score")
        importance_text = f"{float(importance):.2f}" if importance is not None else "N/A"
        metadata = f"来源: {source} | 重要性: {importance_text}"
        comments_url = _extract_comments_url(item.get("summary"))
        if comments_url and comments_url != item["canonical_url"]:
            metadata = f"{metadata} | [讨论]({comments_url})"
        elements.append(
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": (
                        f"**{index}. [{title}]({item['canonical_url']})**\n"
                        f"{summary or 'No summary available.'}\n"
                        f"{metadata}"
                    ),
                },
            }
        )

    return {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "template": "blue",
                "title": {"tag": "plain_text", "content": "Ariadne 信息流摘要"},
            },
            "elements": elements,
        },
    }


def _card_text_without_urls(value: str) -> str:
    text = html_to_text(value)
    text = re.sub(r"\b(?:Article|Comments?) URL:\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"https?://\S+", "", text)
    return normalize_text(text)


def _extract_comments_url(*values: str | None) -> str:
    for value in values:
        text = html_to_text(value or "")
        match = COMMENTS_URL_RE.search(text)
        if match:
            return match.group(1).rstrip(".,;)")
    return ""


def _digest_limit(value) -> int:
    try:
        limit = int(value)
    except (TypeError, ValueError):
        limit = 10
    return min(max(limit, 1), 20)


def _digest_recipient() -> str:
    return f"{get_settings().dry_run_push_recipient}:digest"


def _fetch_digest_items(conn, limit: int, recipient: str, force: bool) -> list[dict]:
    duplicate_filter = ""
    params: list[object] = [recipient, limit]
    if force:
        duplicate_filter = ""
    else:
        duplicate_filter = """
          AND NOT EXISTS (
            SELECT 1
            FROM push_events pe
            WHERE pe.item_id = i.id
              AND pe.status = 'sent'
              AND pe.recipient = %s
          )
        """

    if force:
        params = [limit]

    rows = conn.execute(
        f"""
        SELECT i.id, i.title, i.canonical_url, i.summary, i.created_at,
               s.name AS source_name, ar.importance_score
        FROM items i
        JOIN raw_items r ON r.id = i.raw_item_id
        JOIN sources s ON s.id = r.source_id
        LEFT JOIN LATERAL (
          SELECT importance_score
          FROM analysis_results
          WHERE item_id = i.id
          ORDER BY created_at DESC
          LIMIT 1
        ) ar ON true
        WHERE i.status <> 'ignored'
        {duplicate_filter}
        ORDER BY i.created_at DESC
        LIMIT %s
        """,
        tuple(params),
    ).fetchall()
    return [dict(row) for row in rows]


def _card_template(importance) -> str:
    if importance is None:
        return "blue"
    score = float(importance)
    if score >= 0.75:
        return "red"
    if score >= 0.6:
        return "orange"
    return "blue"


def _analysis_exists(conn, item_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM analysis_results WHERE item_id = %s LIMIT 1",
        (item_id,),
    ).fetchone()
    return row is not None


def _should_skip_push(conn, item_id: str, payload: dict) -> bool:
    return _successful_push_exists(conn, item_id) and not payload.get("force")


def _successful_push_exists(conn, item_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM push_events WHERE item_id = %s AND status = 'sent' LIMIT 1",
        (item_id,),
    ).fetchone()
    return row is not None


def export_obsidian(conn, payload: dict) -> None:
    settings = get_settings()
    if not settings.obsidian_vault_path:
        raise ValueError("OBSIDIAN_VAULT_PATH is not configured")

    item_id = payload["item_id"]
    item = conn.execute(
        """
        SELECT i.*, s.name AS source_name, r.published_at
        FROM items i
        JOIN raw_items r ON r.id = i.raw_item_id
        JOIN sources s ON s.id = r.source_id
        WHERE i.id = %s
        """,
        (item_id,),
    ).fetchone()
    if item is None:
        raise ValueError(f"item not found: {item_id}")

    published = item["published_at"] or datetime.now()
    relative_path = Path("Ariadne") / f"{published:%Y}" / f"{published:%m}" / f"{slugify(item['title'])}.md"
    full_path = Path(settings.obsidian_vault_path) / relative_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    markdown = (
        "---\n"
        f'source: "{item["source_name"]}"\n'
        f'url: "{item["canonical_url"]}"\n'
        f'published: "{published:%Y-%m-%d}"\n'
        f'ariadne_item_id: "{item_id}"\n'
        "---\n\n"
        f"# {item['title']}\n\n"
        "## Summary\n\n"
        f"{item['summary'] or ''}\n\n"
        "## Original\n\n"
        f"{item['canonical_url']}\n"
    )
    full_path.write_text(markdown, encoding="utf-8")
    conn.execute(
        """
        INSERT INTO notes (item_id, path, status)
        VALUES (%s, %s, 'written')
        ON CONFLICT (item_id) DO UPDATE SET path = EXCLUDED.path, status = 'written', updated_at = now()
        """,
        (item_id, str(relative_path)),
    )


if __name__ == "__main__":
    run_forever()
