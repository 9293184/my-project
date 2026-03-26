from __future__ import annotations

from contextlib import contextmanager

import pymysql

from .config import Settings


def build_db_config(settings: Settings) -> dict:
    return {
        "host": settings.db_host,
        "port": settings.db_port,
        "user": settings.db_user,
        "password": settings.db_password,
        "database": settings.db_name,
        "charset": "utf8mb4",
        "cursorclass": pymysql.cursors.DictCursor,
    }


@contextmanager
def db_conn(settings: Settings):
    conn = pymysql.connect(**build_db_config(settings))
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def db_cursor(settings: Settings):
    with db_conn(settings) as conn:
        cursor = conn.cursor()
        try:
            yield conn, cursor
        finally:
            cursor.close()
