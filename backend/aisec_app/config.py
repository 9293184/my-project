import os
from dataclasses import dataclass


def _int_env(name: str, default: int) -> int:
    v = os.getenv(name)
    if v is None or v == "":
        return default
    return int(v)


@dataclass(frozen=True)
class Settings:
    db_host: str
    db_port: int
    db_user: str
    db_password: str
    db_name: str

    @staticmethod
    def from_env() -> "Settings":
        return Settings(
            db_host=os.getenv("DB_HOST", "localhost"),
            db_port=_int_env("DB_PORT", 3306),
            db_user=os.getenv("DB_USER", "root"),
            db_password=os.getenv("DB_PASSWORD", "root"),
            db_name=os.getenv("DB_NAME", "ai_security_system"),
        )
