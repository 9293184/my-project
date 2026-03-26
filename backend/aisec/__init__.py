from __future__ import annotations

import importlib.util
import os
from pathlib import Path


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return int(value)


def create_app():
    # Load legacy Flask app from backend/app.py without requiring backend/ to be a Python package.
    backend_dir = Path(__file__).resolve().parents[1]
    legacy_path = backend_dir / "app.py"
    spec = importlib.util.spec_from_file_location("aisec_legacy_app", legacy_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load legacy backend module from: {legacy_path}")
    legacy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(legacy)

    legacy.DB_CONFIG.update(
        {
            "host": os.getenv("DB_HOST", legacy.DB_CONFIG.get("host", "localhost")),
            "port": _int_env("DB_PORT", int(legacy.DB_CONFIG.get("port", 3306))),
            "user": os.getenv("DB_USER", legacy.DB_CONFIG.get("user", "root")),
            "password": os.getenv("DB_PASSWORD", legacy.DB_CONFIG.get("password", "root")),
            "database": os.getenv(
                "DB_NAME", legacy.DB_CONFIG.get("database", "ai_security_system")
            ),
        }
    )

    return legacy.app
