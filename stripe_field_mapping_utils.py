"""Shared helpers to manage Stripe field mapping metadata."""
from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

BASE_DIR = Path(__file__).resolve().parent
MAPPING_PATH = BASE_DIR / "stripe_field_mapping.json"
INVENTORY_PATH = BASE_DIR / "stripe_field_inventory.json"
DEFAULT_TARGETS = ["dashboard", "airtable", "webhook", "sync"]

_DEFAULT_MAPPING_TEMPLATE: Dict[str, Any] = {
    "meta": {
        "description": "User-defined mapping of Stripe fields to internal destinations.",
        "last_updated": None,
        "targets": DEFAULT_TARGETS,
        "notes": "Run stripe_field_inspector.py to discover all available fields."
    },
    "objects": {}
}

DEFAULT_FIELD_TEMPLATE: Dict[str, Any] = {
    "description": "",
    "use_dashboard": False,
    "use_airtable": False,
    "use_webhook": False,
    "use_sync": False,
    "notes": "",
    "last_example": None,
    "last_type": None,
    "last_count": 0,
}


def _deep_copy(payload: Dict[str, Any]) -> Dict[str, Any]:
    return copy.deepcopy(payload)


def load_mapping() -> Dict[str, Any]:
    if MAPPING_PATH.exists():
        with MAPPING_PATH.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    else:
        data = _deep_copy(_DEFAULT_MAPPING_TEMPLATE)
    data.setdefault("meta", {}).setdefault("targets", DEFAULT_TARGETS)
    data.setdefault("objects", {})
    return data


def save_mapping(mapping: Dict[str, Any], *, touch_timestamp: bool = True) -> None:
    mapping.setdefault("meta", {})
    mapping["meta"].setdefault("targets", DEFAULT_TARGETS)
    if touch_timestamp:
        mapping["meta"]["last_updated"] = datetime.now(timezone.utc).isoformat()
    with MAPPING_PATH.open("w", encoding="utf-8") as handle:
        json.dump(mapping, handle, indent=2, ensure_ascii=False)


def load_inventory(default: Any = None) -> Any:
    if INVENTORY_PATH.exists():
        with INVENTORY_PATH.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    return default


def ensure_object_block(mapping: Dict[str, Any], object_key: str, label: str | None = None) -> Dict[str, Any]:
    objects = mapping.setdefault("objects", {})
    block = objects.setdefault(object_key, {
        "label": label or object_key.replace("_", " ").title(),
        "fields": {}
    })
    block.setdefault("fields", {})
    return block
