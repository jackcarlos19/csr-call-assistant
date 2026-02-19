from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    redis_url: str = "redis://redis:6379/0"
    environment: str = "development"
    log_level: str = "INFO"
    openrouter_api_key: str = ""
    llm_primary_model: str = ""
    llm_fallback_model: str = ""
    pii_redaction_mode: str = "basic"

    class Config:
        env_file = ".env"


settings = Settings()
