import base64
import json
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://ariadne:ariadne@127.0.0.1:5432/ariadne"
    worker_poll_seconds: int = 60
    worker_batch_size: int = 5
    rss_feed_urls: str = ""
    freshrss_feed_urls: str = ""
    rss_auth_username: str = ""
    rss_auth_password: str = ""
    rss_auth_bearer_token: str = ""
    rss_extra_headers: str = ""
    freshrss_api_base_url: str = ""
    freshrss_api_username: str = ""
    freshrss_api_password: str = ""
    freshrss_api_item_limit: int = 50
    feishu_webhook_url: str = ""
    feishu_callback_token: str = ""
    obsidian_vault_path: str = ""
    dry_run_push_recipient: str = Field(default="dry-run")
    push_immediate_min_importance: float = 0.75
    digest_min_importance: float = 0.45
    digest_limit: int = 10
    digest_schedule_times: str = "09:00,17:00"
    digest_schedule_hours: str = "9,17"
    digest_timezone: str = "Asia/Shanghai"
    ingest_max_item_age_days: int = 7
    ingest_max_items_per_feed: int = 100

    @property
    def feed_urls(self) -> list[str]:
        return _split_urls(self.rss_feed_urls) + _split_urls(self.freshrss_feed_urls)

    @property
    def freshrss_api_configured(self) -> bool:
        return bool(self.freshrss_api_base_url and self.freshrss_api_username and self.freshrss_api_password)

    @property
    def rss_request_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.rss_auth_bearer_token:
            headers["Authorization"] = f"Bearer {self.rss_auth_bearer_token}"
        elif self.rss_auth_username or self.rss_auth_password:
            token = base64.b64encode(f"{self.rss_auth_username}:{self.rss_auth_password}".encode("utf-8")).decode(
                "ascii"
            )
            headers["Authorization"] = f"Basic {token}"
        headers.update(_parse_headers(self.rss_extra_headers))
        return headers


@lru_cache
def get_settings() -> Settings:
    return Settings()


def _split_urls(value: str) -> list[str]:
    return [url.strip() for url in value.split(",") if url.strip()]


def _parse_headers(value: str) -> dict[str, str]:
    if not value.strip():
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        return {str(key): str(header_value) for key, header_value in parsed.items() if str(key).strip()}

    headers = {}
    for part in value.split(";"):
        if ":" not in part:
            continue
        key, header_value = part.split(":", 1)
        key = key.strip()
        if key:
            headers[key] = header_value.strip()
    return headers
