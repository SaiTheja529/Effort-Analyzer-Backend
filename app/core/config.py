from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central configuration for the application.
    Loaded from environment variables or .env file.
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    APP_NAME: str = "Effort Analyzer API"
    LOG_LEVEL: str = "INFO"

    # Database
    DATABASE_URL: str

    # GitHub
    GITHUB_TOKEN: str
    GITHUB_CLIENT_ID: str | None = None
    GITHUB_CLIENT_SECRET: str | None = None

    # Gemini
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-2.0-flash-lite"

    # AI request behavior
    AI_REQUEST_TIMEOUT_SECONDS: float = 30.0
    AI_REQUEST_RETRIES: int = 0
    AI_RETRY_BACKOFF_SECONDS: float = 0.5
    AI_SUMMARY_TIMEOUT_SECONDS: float = 40.0

    # Grok (xAI) fallback
    XAI_API_KEY: str | None = None
    XAI_MODEL: str = "grok-3-fast-latest"
    XAI_BASE_URL: str = "https://api.x.ai"

    # Local auth
    AUTH_SECRET_KEY: str = "change-this-local-auth-secret"
    AUTH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7

    # Effort scoring v2
    EFFORT_V2_ENABLED: bool = True
    EFFORT_V2_LLM_ENABLED: bool = True
    EFFORT_V2_MAX_FILES_FOR_LLM: int = 12
    EFFORT_V2_MAX_PATCH_CHARS: int = 9000
    EFFORT_V2_TIMEOUT_SECONDS: float = 35.0


# Singleton settings object
settings = Settings()
