from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    bot_token: SecretStr
    admin_ids: str = ""
    webapp_url: str
    webhook_base_url: str
    webhook_path: str = "/tg/webhook"
    webhook_secret: SecretStr
    redis_url: str
    api_base_url: str
    internal_api_token: SecretStr

    @property
    def admin_id_set(self) -> frozenset[int]:
        return frozenset(int(item) for item in self.admin_ids.split(",") if item.strip())

    @property
    def webhook_url(self) -> str:
        return self.webhook_base_url.rstrip("/") + self.webhook_path
