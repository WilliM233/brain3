"""Application configuration via Pydantic Settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """BRAIN 3.0 application settings, loaded from environment variables / .env file."""

    POSTGRES_USER: str = "brain3"
    POSTGRES_PASSWORD: str = "brain3_dev"
    POSTGRES_DB: str = "brain3_dev"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def database_url(self) -> str:
        """Construct the PostgreSQL connection URL."""
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


settings = Settings()
