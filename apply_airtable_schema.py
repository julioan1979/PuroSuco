import json
from pathlib import Path
from dotenv import load_dotenv
from airtable_client import list_tables, create_table, create_field

load_dotenv()

SCHEMA_FILE = "airtable_schema.json"

TYPE_MAP = {
    "longText": "multilineText",
}

DEFAULT_OPTIONS = {
    "number": {"precision": 0},
    "currency": {"precision": 2, "symbol": "€"},
    "dateTime": {
        "dateFormat": {"name": "iso", "format": "YYYY-MM-DD"},
        "timeFormat": {"name": "24hour", "format": "HH:mm"},
        "timeZone": "utc",
    },
    "checkbox": {"icon": "check", "color": "greenBright"},
}


def _load_schema():
    schema_path = Path(SCHEMA_FILE)
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {SCHEMA_FILE}")
    return json.loads(schema_path.read_text(encoding="utf-8"))


def _map_type(field_type: str) -> str:
    return TYPE_MAP.get(field_type, field_type)


def _default_options(field_type: str):
    return DEFAULT_OPTIONS.get(field_type)


def _get_primary_field(fields_def):
    return next((f for f in fields_def if f.get("primary")), None) or fields_def[0]


def _ensure_table(table_def, existing_tables_by_name):
    name = table_def["name"]
    fields_def = table_def.get("fields", [])

    if name in existing_tables_by_name:
        return existing_tables_by_name[name]["id"], False

    primary = _get_primary_field(fields_def)
    create_payload = {
        "name": name,
        "fields": [
            {
                "name": primary["name"],
                "type": _map_type(primary["type"]),
            }
        ],
    }
    create_table(create_payload)
    return None, True


def _ensure_fields(table_id, table_def, existing_names):
    fields_def = table_def.get("fields", [])

    created_count = 0
    for field in fields_def:
        if field.get("primary"):
            continue
        field_name = field["name"]
        if field_name in existing_names:
            continue

        payload = {
            "name": field_name,
            "type": _map_type(field["type"]),
        }
        if "options" in field:
            payload["options"] = field["options"]
        else:
            default_opts = _default_options(payload["type"])
            if default_opts:
                payload["options"] = default_opts

        try:
            create_field(table_id, payload)
            created_count += 1
            existing_names.add(field_name)
        except Exception as exc:
            detail = ""
            response = getattr(exc, "response", None)
            if response is not None:
                try:
                    detail = response.text
                except Exception:
                    detail = ""
            msg = str(exc)
            if detail:
                msg = f"{msg} | {detail[:200]}"
            print(f"  ✗ Falha ao criar campo '{field_name}': {msg}")

    return created_count


def apply_schema():
    schema = _load_schema()
    base = list_tables()
    existing_tables = {t["name"]: t for t in base.get("tables", [])}
    existing_fields = {
        t["name"]: {f["name"] for f in t.get("fields", [])}
        for t in base.get("tables", [])
    }

    print(f"✓ Base atual tem {len(existing_tables)} tabela(s)")

    total_tables_created = 0
    total_fields_created = 0

    for table_def in schema.get("tables", []):
        table_name = table_def["name"]
        table_id, created = _ensure_table(table_def, existing_tables)

        if created:
            print(f"✓ Tabela criada: {table_name}")
            total_tables_created += 1
            # Refresh after creation to get the real table ID
            base = list_tables()
            existing_tables = {t["name"]: t for t in base.get("tables", [])}
            existing_fields = {
                t["name"]: {f["name"] for f in t.get("fields", [])}
                for t in base.get("tables", [])
            }

        table_id = existing_tables.get(table_name, {}).get("id")
        if not table_id:
            print(f"✗ Falha ao obter ID da tabela '{table_name}'")
            continue

        fields_created = _ensure_fields(
            table_id,
            table_def,
            existing_fields.get(table_name, set()),
        )
        if fields_created:
            print(f"  + {fields_created} campo(s) criado(s) em {table_name}")
            total_fields_created += fields_created
        else:
            print(f"  ⊘ Nenhum campo novo em {table_name}")

    # Warn about extra tables not in schema
    schema_tables = {t["name"] for t in schema.get("tables", [])}
    extra_tables = [t for t in existing_tables.keys() if t not in schema_tables]
    if extra_tables:
        print("\nℹ️ Tabelas extras na base (não fazem parte do schema do projeto):")
        for t in extra_tables:
            print(f"  - {t}")

    print("\nResumo:")
    print(f"  Tabelas criadas: {total_tables_created}")
    print(f"  Campos criados: {total_fields_created}")


if __name__ == "__main__":
    print("=" * 60)
    print("APLICAR SCHEMA AIRTABLE")
    print("=" * 60)
    apply_schema()
    print("=" * 60)
