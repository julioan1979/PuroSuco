import json
import os
from dotenv import load_dotenv
from airtable_client import list_tables, create_table, create_field

load_dotenv()

SCHEMA_FILE = os.getenv("AIRTABLE_SCHEMA_FILE", "airtable_schema.json")


def _load_schema():
    with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _field_payload(field):
    payload = {
        "name": field["name"],
        "type": field["type"],
    }
    return payload


def ensure_schema():
    schema = _load_schema()
    existing = list_tables()
    existing_tables = {t["name"]: t for t in existing.get("tables", [])}

    for table in schema.get("tables", []):
        name = table["name"]
        fields = table.get("fields", [])
        primary = next((f for f in fields if f.get("primary")), None)

        if name not in existing_tables:
            create_payload = {
                "name": name,
                "fields": []
            }
            if primary:
                create_payload["fields"].append(_field_payload(primary))
            else:
                create_payload["fields"].append({"name": "id", "type": "singleLineText"})
            create_table(create_payload)
            existing = list_tables()
            existing_tables = {t["name"]: t for t in existing.get("tables", [])}

        table_id = existing_tables[name]["id"]
        existing_field_names = {f["name"] for f in existing_tables[name].get("fields", [])}
        for field in fields:
            if field.get("primary"):
                continue
            if field["name"] in existing_field_names:
                continue
            create_field(table_id, _field_payload(field))


if __name__ == "__main__":
    try:
        ensure_schema()
        print("Schema aplicado com sucesso.")
    except Exception as exc:
        print("Falha ao aplicar schema via API. Use o arquivo airtable_schema.json manualmente.")
        print(str(exc))
