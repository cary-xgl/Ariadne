# Feishu Message Contract

This document records the current Feishu push message shape used by Ariadne.
Use it as the local reference before changing the message body, card layout, or
feedback behavior.

## Current Mode

Ariadne currently sends messages through a Feishu custom bot webhook.

- Webhook URL comes from `FEISHU_WEBHOOK_URL`.
- The webhook URL must not be committed to the repository.
- When `FEISHU_WEBHOOK_URL` is empty, push jobs run in dry-run mode and still
  record a `push_events` row.
- The current single-item and digest message types are interactive cards:

```json
{
  "msg_type": "interactive",
  "card": {}
}
```

Plain text messages were avoided because Feishu does not render arbitrary HTML
from RSS summaries. The worker strips HTML before building card text.
Bare URLs are also removed from summary and reason text before truncation.
Clickable targets should use button URLs or Markdown links instead of visible
raw URLs.

## Code Ownership

Single-item message body is built in:

```text
src/ariadne/worker.py::_format_push_message
```

Digest message body is built in:

```text
src/ariadne/worker.py::_format_digest_message
```

Push delivery is handled in:

```text
src/ariadne/worker.py::push
src/ariadne/worker.py::push_digest
```

The main format regression test is:

```text
tests/test_push_format.py
```

Update the test whenever the message contract changes.

## Single-Item Card Layout

Current card sections:

1. Header
   - Title: normalized article title, truncated to 80 characters.
   - Template color: derived from `importance_score`.

2. Summary block
   - Label: Chinese text for "summary".
   - Content: `items.summary`, HTML-stripped and truncated to 420 characters.

3. Metadata fields
   - Source label: RSS/FreshRSS source name, truncated to 80 characters.
   - Importance label: latest analysis `importance_score`, formatted as two decimals.

4. Reason block
   - Label: Chinese text for "recommendation reason".
   - Content: latest analysis reason, HTML-stripped and truncated to 240
     characters.

5. Action block
   - Button: Chinese text for "read full article".
   - URL: `items.canonical_url`.

## Field Sources

The push query joins the normalized item, raw item, source, and latest analysis
result.

| Card field | Database source | Fallback |
| --- | --- | --- |
| Title | `items.title` | none |
| Summary | `items.summary` | `No summary available.` |
| Source | `sources.name` | `Unknown source` |
| Importance | `analysis_results.importance_score` | `N/A` |
| Reason | `analysis_results.reason` | `No analysis reason` |
| Read URL | `items.canonical_url` | none |

## Digest Card Layout

Digest cards are created by the `push_digest` job. Use them when the user should
scan a batch instead of receiving one Feishu message per article.

Recommended manual job payload:

```json
{
  "type": "push_digest",
  "payload": {
    "limit": 10,
    "force": true
  }
}
```

Digest behavior:

- `limit` defaults to 10.
- `limit` is clamped to the range 1-20.
- Items are ordered by `items.created_at DESC`.
- Ignored items are excluded.
- Without `force`, items already sent in a digest are skipped.
- With `force`, recent items are sent even if they were already included in a
  previous digest.
- Digest push events use recipient suffix `:digest`.
- Digest pushes do not update `items.status` to `pushed`, so high-value
  single-item push logic can remain independent.

Current digest sections:

1. Header
   - Title: Chinese text for "Ariadne information digest".
   - Template color: `blue`.

2. Intro block
   - Shows how many items are included.

3. Item blocks
   - Numbered title linked to `items.canonical_url`.
   - Short summary, HTML-stripped and truncated.
   - Bare URLs removed from the summary text.
   - Source and importance score.

## Color Rule

Header color is selected by `_card_template`:

| Importance score | Template |
| --- | --- |
| `>= 0.75` | `red` |
| `>= 0.60` | `orange` |
| otherwise | `blue` |
| missing | `blue` |

## Change Checklist

When changing Feishu message format:

1. Update `_format_push_message` or `_format_digest_message`.
2. Add or update `tests/test_push_format.py`.
3. Run `python -m pytest`.
4. Send one forced push job for a known item when testing against a real webhook:

```powershell
Invoke-RestMethod -Method Post http://localhost:8000/internal/jobs `
  -ContentType 'application/json' `
  -Body '{"type":"push","payload":{"item_id":"<item-id>","force":true}}'
```

5. Confirm the new message is readable in Feishu on desktop and mobile.

## Feedback Limitation

Custom bot webhook cards can contain URL buttons. They are enough for readable
article push notifications.

For true in-card feedback such as `useful`, `not_useful`, `read_later`, and
`save_obsidian`, Ariadne should use a Feishu app with event callbacks. The
existing API endpoint is prepared for callbacks:

```text
POST /feishu/events
```

Until the Feishu app flow is added, feedback can still be tested by calling this
endpoint manually with an `item_id` and an `action`.
