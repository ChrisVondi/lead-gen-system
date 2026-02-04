"""
Application configuration using Pydantic Settings.
Loads environment variables from .env file.
"""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ===========================================
    # Application
    # ===========================================
    app_name: str = "Lead Generation System"
    app_env: str = "development"
    debug: bool = True
    secret_key: str = "change-me-in-production"

    # API Settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # ===========================================
    # Database
    # ===========================================
    database_url: str = "postgresql://postgres:postgres@localhost:5432/leadgen"

    # ===========================================
    # AI / Claude API
    # ===========================================
    anthropic_api_key: Optional[str] = None
    claude_model: str = "claude-3-sonnet-20240229"

    # ===========================================
    # AI Ark (Primary B2B Lead Source)
    # ===========================================
    ai_ark_api_key: Optional[str] = None
    ai_ark_base_url: str = "https://api.ai-ark.com/v1"

    # ===========================================
    # Bright Data (LinkedIn Scraping)
    # ===========================================
    bright_data_username: Optional[str] = None
    bright_data_password: Optional[str] = None
    bright_data_host: str = "brd.superproxy.io"
    bright_data_port: int = 22225

    # ===========================================
    # Google Maps API
    # ===========================================
    google_maps_api_key: Optional[str] = None

    # ===========================================
    # Rate Limiting (requests per minute)
    # ===========================================
    google_maps_rate_limit: int = 60
    linkedin_rate_limit: int = 30
    website_rate_limit: int = 100
    ai_ark_rate_limit: int = 100

    # ===========================================
    # Redis
    # ===========================================
    redis_url: str = "redis://localhost:6379/0"

    # ===========================================
    # Streamlit
    # ===========================================
    streamlit_port: int = 8501

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.app_env.lower() == "production"

    @property
    def bright_data_proxy_url(self) -> Optional[str]:
        """Construct Bright Data proxy URL."""
        if self.bright_data_username and self.bright_data_password:
            return (
                f"http://{self.bright_data_username}:{self.bright_data_password}"
                f"@{self.bright_data_host}:{self.bright_data_port}"
            )
        return None


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    Use this function to access settings throughout the application.
    """
    return Settings()


# Convenience alias
settings = get_settings()
