import json
import os
from datetime import datetime, timezone
from typing import Any, Dict

DEFAULT_CACHE = {
    "charges": {},
    "sessions": {},
    "updated_at": None,
}


def get_cache_path() -> str:
    base_dir = os.path.dirname(__file__)
    return os.getenv(
        "STRIPE_PAID_CACHE_PATH",
        os.path.join(base_dir, "data", "stripe_paid_cache.json")
    )


def _ensure_cache_dir(cache_path: str) -> None:
    cache_dir = os.path.dirname(cache_path)
    if cache_dir and not os.path.exists(cache_dir):
        os.makedirs(cache_dir, exist_ok=True)


def load_paid_cache(path: str = None) -> Dict[str, Any]:
    cache_path = path or get_cache_path()
    if not os.path.exists(cache_path):
        return dict(DEFAULT_CACHE)
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return dict(DEFAULT_CACHE)
        data.setdefault("charges", {})
        data.setdefault("sessions", {})
        data.setdefault("updated_at", None)
        return data
    except Exception:
        return dict(DEFAULT_CACHE)


def _write_cache(cache_path: str, data: Dict[str, Any]) -> None:
    _ensure_cache_dir(cache_path)
    tmp_path = f"{cache_path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp_path, cache_path)


def _touch_updated_at(data: Dict[str, Any]) -> None:
    data["updated_at"] = datetime.now(tz=timezone.utc).isoformat()


def upsert_paid_charge(charge: Dict[str, Any], path: str = None) -> None:
    if not isinstance(charge, dict) or not charge.get("id"):
        return
    cache_path = path or get_cache_path()
    data = load_paid_cache(cache_path)
    data.setdefault("charges", {})
    data["charges"][charge["id"]] = charge
    _touch_updated_at(data)
    _write_cache(cache_path, data)


def upsert_paid_session(session: Dict[str, Any], path: str = None) -> None:
    if not isinstance(session, dict) or not session.get("id"):
        return
    cache_path = path or get_cache_path()
    data = load_paid_cache(cache_path)
    data.setdefault("sessions", {})
    data["sessions"][session["id"]] = session
    _touch_updated_at(data)
    _write_cache(cache_path, data)
