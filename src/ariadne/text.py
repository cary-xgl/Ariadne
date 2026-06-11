from __future__ import annotations

import hashlib
import html
from html.parser import HTMLParser
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


TRACKING_PREFIXES = ("utm_",)
TRACKING_PARAMS = {"fbclid", "gclid", "igshid", "mc_cid", "mc_eid"}


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonicalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower() or "https"
    netloc = parts.netloc.lower()
    path = re.sub(r"/+$", "", parts.path) or "/"
    query_pairs = []

    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        key_lower = key.lower()
        if key_lower in TRACKING_PARAMS:
            continue
        if any(key_lower.startswith(prefix) for prefix in TRACKING_PREFIXES):
            continue
        query_pairs.append((key, value))

    query = urlencode(sorted(query_pairs), doseq=True)
    return urlunsplit((scheme, netloc, path, query, ""))


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data:
            self.parts.append(data)

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"br", "div", "li", "p", "tr"}:
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"div", "li", "p", "tr"}:
            self.parts.append(" ")

    def get_text(self) -> str:
        return normalize_text(" ".join(self.parts))


def html_to_text(value: str) -> str:
    if not value:
        return ""
    parser = _HTMLTextExtractor()
    parser.feed(html.unescape(value))
    parser.close()
    return parser.get_text()


def slugify(value: str, fallback: str = "item") -> str:
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", value).strip("-").lower()
    return slug[:80] or fallback
