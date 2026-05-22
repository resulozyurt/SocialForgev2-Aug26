from functools import lru_cache
from typing import Optional
from cryptography.fernet import Fernet, InvalidToken
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    bootstrap_anthropic_key: Optional[str] = None
    bootstrap_openai_key: Optional[str] = None
    bootstrap_replicate_key: Optional[str] = None
    bootstrap_apify_key: Optional[str] = None

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


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