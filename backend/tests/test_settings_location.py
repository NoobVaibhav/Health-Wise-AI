"""The settings file is found from the backend folder, so starting the server from the project root (as the dev launcher does) reads the same .env as starting it inside backend/."""
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]


def test_env_file_is_read_whatever_the_working_directory():
    from app.core.config import Settings

    env_file = Path(Settings.model_config["env_file"])
    assert env_file.is_absolute() and env_file == BACKEND / ".env"
