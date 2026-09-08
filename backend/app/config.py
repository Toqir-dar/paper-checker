from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "paper_checker"

    groq_api_keys_csv: str = Field(default="", validation_alias="GROQ_API_KEYS")
    groq_models_csv: str = Field(
        default="openai/gpt-oss-120b,openai/gpt-oss-20b,qwen/qwen3.6-27b",
        validation_alias="GROQ_MODELS",
    )

    gemini_api_keys_csv: str = Field(default="", validation_alias="GEMINI_API_KEYS")
    gemini_models_csv: str = Field(
        default="gemini-2.5-flash,gemini-2.0-flash,gemini-1.5-flash,gemini-2.0-flash-lite",
        validation_alias="GEMINI_MODELS",
    )

    cors_origins_csv: str = Field(
        default="http://localhost:4200,https://paper-checker-fvwt.vercel.app,https://paper-checker-rust.vercel.app",
        validation_alias="CORS_ORIGINS",
    )
    # Vercel URLs for this project vary in shape: the stable production alias
    # (paper-checker-fvwt.vercel.app) has no hash, while preview/production
    # deployment URLs carry a per-deployment hash and team suffix
    # (paper-checker-fvwt-8jxlygvhl-toqir-dars-projects.vercel.app) that changes
    # on every deploy. This regex allows any such URL without repeated config changes.
    cors_origin_regex: str = Field(
        default=r"^https://paper-checker(-[a-zA-Z0-9]+)*\.vercel\.app$",
        validation_alias="CORS_ORIGIN_REGEX",
    )

    api_key: str = Field(default="", validation_alias="API_KEY")
    app_environment: str = Field(default="development", validation_alias="APP_ENV")
    auth_secret: str = Field(default="", validation_alias="AUTH_SECRET")
    auth_cookie_name: str = Field(default="paper_checker_session", validation_alias="AUTH_COOKIE_NAME")
    auth_csrf_cookie_name: str = Field(default="paper_checker_csrf", validation_alias="AUTH_CSRF_COOKIE_NAME")
    auth_refresh_cookie_name: str = Field(default="paper_checker_refresh", validation_alias="AUTH_REFRESH_COOKIE_NAME")
    auth_login_limit: int = Field(default=10, validation_alias="AUTH_LOGIN_LIMIT")
    auth_login_window_seconds: int = Field(default=60, validation_alias="AUTH_LOGIN_WINDOW_SECONDS")
    auth_signup_limit: int = Field(default=5, validation_alias="AUTH_SIGNUP_LIMIT")
    auth_signup_window_seconds: int = Field(default=3600, validation_alias="AUTH_SIGNUP_WINDOW_SECONDS")
    max_upload_bytes: int = Field(default=15 * 1024 * 1024, validation_alias="MAX_UPLOAD_BYTES")
    max_document_pages: int = Field(default=50, validation_alias="MAX_DOCUMENT_PAGES")
    model_requests_per_minute: int = Field(default=15, validation_alias="MODEL_REQUESTS_PER_MINUTE")
    model_requests_per_day: int = Field(default=500, validation_alias="MODEL_REQUESTS_PER_DAY")

    @property
    def groq_api_keys(self) -> list[str]:
        return [key.strip() for key in self.groq_api_keys_csv.split(",") if key.strip()]

    @property
    def groq_models(self) -> list[str]:
        return [model.strip() for model in self.groq_models_csv.split(",") if model.strip()]

    @property
    def gemini_api_keys(self) -> list[str]:
        return [key.strip() for key in self.gemini_api_keys_csv.split(",") if key.strip()]

    @property
    def gemini_models(self) -> list[str]:
        return [model.strip() for model in self.gemini_models_csv.split(",") if model.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins_csv.split(",") if origin.strip()]

    @property
    def auth_cookie_secure(self) -> bool:
        return self.app_environment.strip().lower() in {"production", "prod"}

    @property
    def auth_cookie_samesite(self) -> str:
        return "none" if self.auth_cookie_secure else "lax"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
