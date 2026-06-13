from __future__ import annotations

import email.utils
import json
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone

from ariadne.text import html_to_text, normalize_text, sha256_text


@dataclass(frozen=True)
class FeedItem:
    source_name: str
    source_url: str
    external_id: str
    url: str
    title: str
    author: str | None
    published_at: datetime | None
    content: str
    raw_payload: dict[str, str | None]

    @property
    def content_hash(self) -> str:
        return sha256_text(f"{self.title}\n{self.url}\n{self.content}")


def fetch_feed(url: str, timeout: int = 20, headers: dict[str, str] | None = None) -> list[FeedItem]:
    request_headers = {"User-Agent": "Ariadne/0.1", **(headers or {})}
    request = urllib.request.Request(url, headers=request_headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read()
    return parse_feed(body, url)


def parse_feed(body: bytes, source_url: str) -> list[FeedItem]:
    root = ET.fromstring(body)
    if root.tag.endswith("rss"):
        return _parse_rss(root, source_url)
    if root.tag.endswith("feed"):
        return _parse_atom(root, source_url)
    raise ValueError("Unsupported feed format")


def _parse_rss(root: ET.Element, source_url: str) -> list[FeedItem]:
    channel = root.find("channel")
    source_name = _text(channel, "title") if channel is not None else source_url
    items = []
    for entry in root.findall("./channel/item"):
        link = normalize_text(_text(entry, "link") or "")
        title = normalize_text(_text(entry, "title") or link)
        content = html_to_text(
            _text(entry, "description")
            or _text(entry, "{http://purl.org/rss/1.0/modules/content/}encoded")
            or ""
        )
        external_id = normalize_text(_text(entry, "guid") or link or sha256_text(title))
        published_at = _parse_datetime(_text(entry, "pubDate"))
        author = _text(entry, "author") or _text(entry, "{http://purl.org/dc/elements/1.1/}creator")
        if link:
            items.append(
                FeedItem(
                    source_name=source_name or source_url,
                    source_url=source_url,
                    external_id=external_id,
                    url=link,
                    title=title,
                    author=author,
                    published_at=published_at,
                    content=content,
                    raw_payload=_payload(entry),
                )
            )
    return items


def _parse_atom(root: ET.Element, source_url: str) -> list[FeedItem]:
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    source_name = _text(root, "atom:title", ns) or source_url
    items = []
    for entry in root.findall("atom:entry", ns):
        link = _atom_link(entry, ns)
        title = normalize_text(_text(entry, "atom:title", ns) or link)
        content = html_to_text(_text(entry, "atom:content", ns) or _text(entry, "atom:summary", ns) or "")
        external_id = normalize_text(_text(entry, "atom:id", ns) or link or sha256_text(title))
        published_at = _parse_datetime(_text(entry, "atom:published", ns) or _text(entry, "atom:updated", ns))
        author = _text(entry, "atom:author/atom:name", ns)
        if link:
            items.append(
                FeedItem(
                    source_name=source_name,
                    source_url=source_url,
                    external_id=external_id,
                    url=link,
                    title=title,
                    author=author,
                    published_at=published_at,
                    content=content,
                    raw_payload=_payload(entry),
                )
            )
    return items


def _text(element: ET.Element | None, path: str, ns: dict[str, str] | None = None) -> str | None:
    if element is None:
        return None
    found = element.find(path, ns or {})
    if found is None or found.text is None:
        return None
    return found.text.strip()


def _atom_link(entry: ET.Element, ns: dict[str, str]) -> str:
    for link in entry.findall("atom:link", ns):
        href = link.attrib.get("href")
        rel = link.attrib.get("rel", "alternate")
        if href and rel == "alternate":
            return href.strip()
    return ""


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError):
        parsed = None
    if parsed is None:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _payload(entry: ET.Element) -> dict[str, str | None]:
    return json.loads(json.dumps({child.tag: child.text for child in list(entry)}))
