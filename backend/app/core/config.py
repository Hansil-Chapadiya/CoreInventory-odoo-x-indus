"""
Application configuration loaded from environment variables.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "CoreInventory"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/core_inventory"
    DATABASE_ECHO: bool = False

    # Auth
    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Email (Gmail SMTP via App Password)
    MAIL_USERNAME: str = ""           # youraddress@gmail.com
    MAIL_PASSWORD: str = ""           # Gmail App Password (16 chars)
    MAIL_FROM: str = ""               # Sender address (same as MAIL_USERNAME)
    MAIL_FROM_NAME: str = "CoreInventory"

    # CORS (React frontend)
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
