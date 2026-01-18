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
    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemini-3-flash-preview"


# Singleton settings object
settings = Settings()
