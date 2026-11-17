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
    GOOGLE_CLIENT_IDS: str = ""  # extra accepted client ids, comma separated
    GOOGLE_WEB_CLIENT_ID: str = ""  # used by the website's Google button (public)
    GOOGLE_IOS_CLIENT_ID: str = ""
    GOOGLE_ANDROID_CLIENT_ID: str = ""
    APPLE_BUNDLE_IDS: str = ""  # comma separated

    # Firebase email-link ("magic link") sign-in. These web config values are public by design.
    FIREBASE_PROJECT_ID: str = ""
    FIREBASE_API_KEY: str = ""
    FIREBASE_AUTH_DOMAIN: str = ""  # e.g. my-project.firebaseapp.com
    EMAIL_LINK_CONTINUE_URL: str = "http://localhost:8001/auth/email-link"  # page that finishes the sign-in

    # Single sign-on (OpenID Connect): Microsoft Entra ID, Google Workspace, Okta, Auth0, Keycloak...
    OIDC_ISSUER: str = ""  # e.g. https://login.microsoftonline.com/<tenant-id>/v2.0
    OIDC_CLIENT_ID: str = ""
    OIDC_CLIENT_SECRET: str = ""
    OIDC_SCOPES: str = "openid email profile"
    OIDC_LABEL: str = "Sign in with company SSO"
    API_PUBLIC_URL: str = "http://localhost:8000"  # the IdP redirects back to {API_PUBLIC_URL}/auth/sso/callback
    # Where a finished SSO sign-in may return to (URL prefixes). Remove exp:// in production.
    SSO_ALLOWED_REDIRECTS: str = ("http://localhost:8001/,http://localhost:8002/,http://localhost:8003/,"
                                  "freshflow://,exp://")
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_FROM_NUMBER: str = ""  # only for plain SMS (not needed with Verify)
    # Twilio Verify sends and checks the OTP itself (recommended; handles India's DLT SMS rules)
    TWILIO_VERIFY_SERVICE_SID: str = ""  # starts with VA
    # Free option: the "SMS Gateway for Android" app (sms-gate.app) sends texts from your own phone's SIM.
    # Cloud mode URL below; for local mode use http://<phone-ip>:8080/message
    SMSGATE_URL: str = "https://api.sms-gate.app/3rdparty/v1/message"
    SMSGATE_USERNAME: str = ""
    SMSGATE_PASSWORD: str = ""
    PHONE_DEFAULT_COUNTRY_CODE: str = "+91"  # added to 10-digit numbers typed without a country code

    # Optional Redis for multi-instance websocket fan-out
    REDIS_URL: str = ""

    @property
    def google_audiences(self) -> list[str]:
        ids = [self.GOOGLE_WEB_CLIENT_ID, self.GOOGLE_IOS_CLIENT_ID, self.GOOGLE_ANDROID_CLIENT_ID,
               *self.GOOGLE_CLIENT_IDS.split(",")]
        return sorted({i.strip() for i in ids if i and i.strip()})

    @property
    def sso_allowed_redirects(self) -> list[str]:
        return [p.strip() for p in self.SSO_ALLOWED_REDIRECTS.split(",") if p.strip()]

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
