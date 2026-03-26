from __future__ import annotations

from datetime import datetime


def dt_to_str(value):
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return value


def normalize_datetimes(obj):
    if isinstance(obj, dict):
        return {k: normalize_datetimes(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [normalize_datetimes(v) for v in obj]
    return dt_to_str(obj)
