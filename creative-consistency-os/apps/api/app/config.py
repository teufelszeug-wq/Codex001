from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Creative Consistency OS API"
    app_version: str = "0.1.0"
    api_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./data/creative_consistency.db"
    cors_origins: str = "http://localhost:3000"

    model_config = SettingsConfigDict(env_prefix="CCOS_", env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()


def ensure_local_data_dir() -> None:
    if settings.database_url.startswith("sqlite"):
        Path("data").mkdir(parents=True, exist_ok=True)
