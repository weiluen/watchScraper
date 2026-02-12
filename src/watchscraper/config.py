from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    database_url: str = (
        "postgresql://watchscraper:watchscraper@localhost:5433/watchscraper"
    )

    # eBay
    ebay_app_id: str = ""
    ebay_cert_id: str = ""

    # WatchCharts
    watchcharts_api_key: str = ""

    # Scraper tuning
    scrape_delay_min: float = 2.0
    scrape_delay_max: float = 5.0

    log_level: str = "INFO"


settings = Settings()
