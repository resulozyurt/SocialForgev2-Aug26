from functools import lru_cache
from typing import Optional
from cryptography.fernet import Fernet, InvalidToken
from pydantic_settings import BaseSettings, SettingsConfigDict


def _normalize_db_url(url: str) -> str:
    """Railway/Heroku hand out `postgres://` or `postgresql://` URLs, but our
    async engine needs the asyncpg driver. Normalize the scheme so the same
    DATABASE_URL works locally and in production."""
    if not url:
        return url
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = "development"
    app_secret_key: str = "dev-secret-change-in-production"
    debug: bool = True

    fernet_key: str = ""
    database_url: str = ""
    redis_url: str = ""

    # Admin panel (HTTP Basic) — protects every mutating/admin endpoint.
    admin_username: str = "admin"
    admin_password: str = "change-me"

    # Comma-separated list of browser origins allowed by CORS.
    cors_origins: str = "http://localhost:3000"

    # Bootstrap provider keys (optional fallbacks; per-brand keys live encrypted in DB).
    bootstrap_anthropic_key: Optional[str] = None
    bootstrap_openai_key: Optional[str] = None
    bootstrap_apify_key: Optional[str] = None

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def async_database_url(self) -> str:
        """DATABASE_URL normalized to the asyncpg driver."""
        return _normalize_db_url(self.database_url)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


class EncryptionManager:
    def __init__(self, fernet_key: str) -> None:
        self._fernet = Fernet(fernet_key.encode())

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken as exc:
            raise ValueError("Decryption failed — wrong key or corrupted data.") from exc


def get_encryption_manager() -> EncryptionManager:
    return EncryptionManager(get_settings().fernet_key)
