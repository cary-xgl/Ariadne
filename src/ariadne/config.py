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


@lru_cache
def get_settings() -> Settings:
    return Settings()


def _split_urls(value: str) -> list[str]:
    return [url.strip() for url in value.split(",") if url.strip()]
