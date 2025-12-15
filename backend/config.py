from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    app_secret_key: str = "change-me-in-production"
    app_pin: str = "1234"
    base_url: str = "http://localhost:8001"
    frontend_url: str = "http://localhost:8000"

    # Microsoft
    microsoft_client_id: str = ""
    microsoft_client_secret: str = ""

    # Google
    google_client_id: str = ""
    google_client_secret: str = ""

    # TickTick
    ticktick_client_id: str = ""
    ticktick_client_secret: str = ""

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/kanban.db"

    # Token encryption key (derived from app_secret_key)
    @property
    def encryption_key(self) -> bytes:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        import base64

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"email-kanban-salt",
            iterations=100000,
        )
        return base64.urlsafe_b64encode(kdf.derive(self.app_secret_key.encode()))

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
