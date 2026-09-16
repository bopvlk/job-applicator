from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        yaml_file="config.yaml",
        env_file=".env",
        extra="ignore",
    )

    # static (config.yaml)
    trusted_emails: list[str]
    target_sites: list[str]
    ai_model: list[str]
    mistral_model: list[str]
    run_interval_minutes: int
    min_tavily_score: float = 0.4
    cron_hours: str = "9,12,16,20"

    # secrets (env / .env)
    telegram_token: str
    database_uri: str
    smtp_host: str
    smtp_port: int = 587
    smtp_user: str
    smtp_pass: str
    smtp_from: str

    # ai api keys (env / .env)
    ai_api_key: str  # gemini
    mistral_api_key: str | None = None

    # external APIs (env / .env)
    serp_api_key: str | None = None
    tavily_api_key: str
    jina_api_key: str | None = None
    qdrant_url: str
    qdrant_api_key: str

    # Observability (env / .env)
    sentry_dsn: str | None = None
    grafana_loki_url: str | None = None
    grafana_loki_user: str | None = None
    grafana_loki_token: str | None = None

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            YamlConfigSettingsSource(settings_cls),
            file_secret_settings,
        )


config = Config()
