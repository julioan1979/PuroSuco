"""Utility script to inventory Stripe object fields and keep stripe_field_mapping.json in sync."""
import argparse
import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable

import stripe
from dotenv import load_dotenv

from stripe_field_mapping_utils import (
    DEFAULT_FIELD_TEMPLATE,
    INVENTORY_PATH,
    MAPPING_PATH,
    ensure_object_block,
    load_mapping,
    save_mapping,
)

BASE_DIR = Path(__file__).resolve().parent

OBJECT_CONFIG = {
    "charges": {
        "label": "Charge",
        "list_callable": stripe.Charge.list,
        "params": {"expand": ["data.customer"]},
    },
    "checkout_sessions": {
        "label": "Checkout Session",
        "list_callable": stripe.checkout.Session.list,
        "params": {"expand": ["data.customer", "data.customer_details"]},
    },
    "payment_intents": {
        "label": "Payment Intent",
        "list_callable": stripe.PaymentIntent.list,
        "params": {"expand": ["data.charges"]},
    },
    "customers": {
        "label": "Customer",
        "list_callable": stripe.Customer.list,
        "params": {},
    },
    "invoices": {
        "label": "Invoice",
        "list_callable": stripe.Invoice.list,
        "params": {"expand": ["data.customer", "data.lines.data.price"]},
    },
    "payouts": {
        "label": "Payout",
        "list_callable": stripe.Payout.list,
        "params": {},
    },
    "events": {
        "label": "Event",
        "list_callable": stripe.Event.list,
        "params": {},
    },
}


def _example_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return f"<{type(value).__name__} len={len(value)}>"
    if isinstance(value, dict):
        return f"<{type(value).__name__} keys={len(value)}>"
    return str(value)


def _record(path: str, value: Any, collector: Dict[str, Dict[str, Any]]):
    if not path:
        return
    entry = collector.setdefault(path, {
        "types": set(),
        "examples": [],
        "count": 0,
    })
    entry["types"].add(type(value).__name__ if value is not None else "NoneType")
    if len(entry["examples"]) < 3:
        entry["examples"].append(_example_value(value))
    entry["count"] += 1


def _flatten(value: Any, prefix: str, collector: Dict[str, Dict[str, Any]]):
    if isinstance(value, dict):
        if not value:
            _record(prefix, {}, collector)
        for key, sub in value.items():
            new_prefix = f"{prefix}.{key}" if prefix else key
            _flatten(sub, new_prefix, collector)
    elif isinstance(value, list):
        _record(prefix, value, collector)
        element_prefix = f"{prefix}[]" if prefix else "[]"
        for item in value[:3]:
            _flatten(item, element_prefix, collector)
    else:
        _record(prefix, value, collector)


def _fetch_objects(name: str, limit: int) -> Iterable[dict]:
    config = OBJECT_CONFIG[name]
    params = dict(config.get("params", {}))
    params.setdefault("limit", min(limit, 100))
    data = []
    for item in config["list_callable"](**params).auto_paging_iter():
        data.append(item)
        if len(data) >= limit:
            break
    return data


def _save_json(path: Path, payload: Any):
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)


def inspect_objects(object_names, limit):
    inventory = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "limit_per_object": limit,
        "objects": {}
    }
    for obj_name in object_names:
        records = _fetch_objects(obj_name, limit)
        collector = {}
        for record in records:
            _flatten(record, "", collector)
        fields = {}
        for path, info in collector.items():
            fields[path] = {
                "types": sorted(list(info["types"])),
                "examples": info["examples"],
                "count": info["count"],
            }
        inventory["objects"][obj_name] = {
            "label": OBJECT_CONFIG[obj_name]["label"],
            "sample_count": len(records),
            "fields": fields
        }
    return inventory


def update_mapping(inventory):
    mapping = load_mapping()
    for obj_name, obj_data in inventory.get("objects", {}).items():
        label = OBJECT_CONFIG.get(obj_name, {}).get("label")
        obj_mapping = ensure_object_block(mapping, obj_name, label=label)
        fields = obj_mapping.setdefault("fields", {})
        for field_path, info in obj_data.get("fields", {}).items():
            template = dict(DEFAULT_FIELD_TEMPLATE)
            template.update(fields.get(field_path, {}))
            template["last_example"] = info.get("examples", [None])[0]
            template["last_type"] = info.get("types", [None])[0]
            template["last_count"] = info.get("count", 0)
            fields[field_path] = template
    save_mapping(mapping, touch_timestamp=False)


def main():
    parser = argparse.ArgumentParser(description="Inventory Stripe object fields and update local mapping file.")
    parser.add_argument("--objects", nargs="+", choices=sorted(OBJECT_CONFIG.keys()), default=list(OBJECT_CONFIG.keys()), help="Object types to inspect")
    parser.add_argument("--limit", type=int, default=50, help="Max records to pull per object")
    parser.add_argument("--no-update-mapping", action="store_true", help="Skip updating stripe_field_mapping.json")
    args = parser.parse_args()

    load_dotenv()
    api_key = os.getenv("STRIPE_API_KEY")
    if not api_key:
        raise SystemExit("STRIPE_API_KEY not set. Configure .env before running this script.")
    stripe.api_key = api_key

    inventory = inspect_objects(args.objects, args.limit)
    _save_json(INVENTORY_PATH, inventory)
    print(f"Saved inventory to {INVENTORY_PATH.relative_to(BASE_DIR)}")

    if not args.no_update_mapping:
        update_mapping(inventory)
        print(f"Updated mapping file at {MAPPING_PATH.relative_to(BASE_DIR)}")
    else:
        print("Skipped mapping update (per flag).")


if __name__ == "__main__":
    main()
