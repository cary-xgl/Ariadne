from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from ariadne.rss import FeedItem
from ariadne.text import html_to_text, normalize_text, sha256_text


def fetch_freshrss_items(
    base_url: str,
    username: str,
    password: str,
    limit: int = 50,
    timeout: int = 20,
) -> list[FeedItem]:
    base_url = base_url.rstrip("/")
    auth_token = _client_login(base_url, username, password, timeout)
    payload = _get_json(
        f"{base_url}/reader/api/0/stream/contents/reading-list?n={_item_limit(limit)}",
        {"Authorization": f"GoogleLogin auth={auth_token}"},
        timeout,
    )
    return [_item_from_entry(entry, base_url) for entry in payload.get("items", []) if _entry_url(entry)]


def _client_login(base_url: str, username: str, password: str, timeout: int) -> str:
    body = urllib.parse.urlencode(
        {
            "Email": username,
            "Passwd": password,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url}/accounts/ClientLogin",
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Ariadne/0.1",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        text = response.read().decode("utf-8", "replace")
    for line in text.splitlines():
        if line.startswith("Auth="):
            return line.split("=", 1)[1].strip()
    raise ValueError("FreshRSS API login did not return an auth token")


def _get_json(url: str, headers: dict[str, str], timeout: int) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "Ariadne/0.1", **headers})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _item_from_entry(entry: dict[str, Any], source_url: str) -> FeedItem:
    url = _entry_url(entry)
    title = normalize_text(str(entry.get("title") or url))
    content = html_to_text(_entry_content(entry))
    source_name = _origin_title(entry) or source_url
    published_at = _entry_datetime(entry)
    external_id = normalize_text(str(entry.get("id") or url or sha256_text(title)))
    return FeedItem(
        source_name=source_name,
        source_url=source_url,
        external_id=external_id,
        url=url,
        title=title,
        author=_entry_author(entry),
        published_at=published_at,
        content=content,
        raw_payload=_string_payload(entry),
    )


def _entry_url(entry: dict[str, Any]) -> str:
    for key in ("canonical", "alternate"):
        values = entry.get(key)
        if isinstance(values, list):
            for value in values:
                if isinstance(value, dict) and value.get("href"):
                    return str(value["href"]).strip()
    return str(entry.get("id") or "").strip()


def _entry_content(entry: dict[str, Any]) -> str:
    for key in ("content", "summary"):
        value = entry.get(key)
        if isinstance(value, dict) and value.get("content"):
            return str(value["content"])
    return ""


def _origin_title(entry: dict[str, Any]) -> str | None:
    origin = entry.get("origin")
    if isinstance(origin, dict) and origin.get("title"):
        return str(origin["title"])
    return None


def _entry_author(entry: dict[str, Any]) -> str | None:
    author = entry.get("author")
    return str(author) if author else None


def _entry_datetime(entry: dict[str, Any]) -> datetime | None:
    value = entry.get("published") or entry.get("updated")
    if not isinstance(value, int | float):
        return None
    return datetime.fromtimestamp(value, tz=timezone.utc)


def _string_payload(entry: dict[str, Any]) -> dict[str, str | None]:
    return {
        str(key): json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
        for key, value in entry.items()
    }


def _item_limit(value: int) -> int:
    return min(max(int(value), 1), 200)
