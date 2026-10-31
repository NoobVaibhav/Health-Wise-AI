"""Application settings, loaded from environment variables / .env file."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # SQLite for local development; use a postgresql:// URL in production.
    database_url: str = f"sqlite:///{BACKEND_DIR / 'healthwise.db'}"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24
    bcrypt_rounds: int = 12  # password hashing cost (tests lower it for speed)

    upload_dir: str = str(BACKEND_DIR / "uploads")
    max_file_size: int = 10 * 1024 * 1024  # bytes

    # Optional LLM. If empty the app uses deterministic explanations.
    llm_api_key: str = ""
    llm_api_url: str = "https://api.anthropic.com/v1/messages"
    llm_model: str = "claude-haiku-4-5-20251001"

    # The starting password of every new account. The person logs in with it once and must then choose their own
    # (the server blocks everything else until they do). Change it here; it must have a letter and a number, 8+ characters.
    default_password: str = "Welcome@123"

    # Patient assistant (chat + voice)
    # The letterhead of printed prescriptions. Empty = not shown (nothing is invented).
    hospital_name: str = ""
    hospital_address: str = ""
    hospital_phone: str = ""
    hospital_email: str = ""

    emergency_number: str = "112"               # shown in emergency guidance
    assistant_retention_days: int = 90          # chats older than this are deleted
    assistant_rate_per_minute: int = 20         # messages per patient per minute

    # Optional path to tesseract.exe if it is not on PATH.
    tesseract_cmd: str = ""

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"


@lru_cache
def get_settings() -> Settings:
    return Settings()
