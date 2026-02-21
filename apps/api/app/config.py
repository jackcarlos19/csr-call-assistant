from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    # Redis support planned for WS pub/sub at scale (>10k concurrent connections)
    environment: str = "development"
    log_level: str = "INFO"
    openrouter_api_key: str = ""
    llm_primary_model: str = ""
    llm_fallback_model: str = ""
    pii_redaction_mode: str = "basic"
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_api_key_sid: str = ""
    twilio_api_key_secret: str = ""
    twilio_phone_number: str = ""
    twilio_stream_ws_base_url: str = "ws://localhost:8000"

    class Config:
        env_file = ".env"


settings = Settings()
