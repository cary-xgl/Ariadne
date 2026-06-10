from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://ariadne:ariadne@localhost:5432/ariadne"
    worker_poll_seconds: int = 5
    worker_batch_size: int = 5
    rss_feed_urls: str = ""
    feishu_webhook_url: str = ""
    feishu_callback_token: str = ""
    obsidian_vault_path: str = ""
    dry_run_push_recipient: str = Field(default="dry-run")

    @property
    def feed_urls(self) -> list[str]:
        return [url.strip() for url in self.rss_feed_urls.split(",") if url.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
