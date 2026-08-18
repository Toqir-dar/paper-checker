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
        default="gemini-3.6-flash,gemini-3.5-flash-lite",
        validation_alias="GEMINI_MODELS",
    )

    openrouter_api_keys_csv: str = Field(default="", validation_alias="OPENROUTER_API_KEYS")
    openrouter_vision_models_csv: str = Field(
        default="google/gemma-4-31b-it:free,google/gemma-4-26b-a4b-it:free,nvidia/nemotron-nano-12b-v2-vl:free",
        validation_alias="OPENROUTER_VISION_MODELS",
    )

    cors_origins_csv: str = Field(default="http://localhost:4200", validation_alias="CORS_ORIGINS")

    api_key: str = Field(default="", validation_alias="API_KEY")

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
    def openrouter_api_keys(self) -> list[str]:
        return [key.strip() for key in self.openrouter_api_keys_csv.split(",") if key.strip()]

    @property
    def openrouter_vision_models(self) -> list[str]:
        return [model.strip() for model in self.openrouter_vision_models_csv.split(",") if model.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins_csv.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
