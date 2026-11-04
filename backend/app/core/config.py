"""Central configuration, read from environment variables / .env file."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "FreshFlow"
    DEBUG: bool = True
    DATABASE_URL: str = "sqlite:///./freshflow.db"
    SECRET_KEY: str = "change-me-in-production-please-32-bytes-min"
    ACCESS_TOKEN_MINUTES: int = 60 * 24 * 7
    CORS_ORIGINS: str = "*"

    # Commerce
    CURRENCY: str = "INR"
    TAX_RATE: float = 0.05
    DELIVERY_FEE: float = 25.0
    FREE_DELIVERY_ABOVE: float = 199.0
    PICKUP_SLOT_MINUTES: int = 30
    PICKUP_SLOT_CAPACITY: int = 10
    RECEIPT_VALID_HOURS: int = 3

    # Payments: "mock" runs the whole flow without real gateway keys.
    PAYMENTS_MODE: str = "mock"  # mock | live
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    PAYPAL_CLIENT_ID: str = ""
    PAYPAL_CLIENT_SECRET: str = ""
    PAYPAL_BASE_URL: str = "https://api-m.sandbox.paypal.com"
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""

    # Social / phone login
    GOOGLE_CLIENT_IDS: str = ""  # comma separated (web, ios, android client ids)
    APPLE_BUNDLE_IDS: str = ""  # comma separated
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_FROM_NUMBER: str = ""

    # Optional Redis for multi-instance websocket fan-out
    REDIS_URL: str = ""

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
