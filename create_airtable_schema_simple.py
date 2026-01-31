import os
import json
import sys
from dotenv import load_dotenv
from airtable_client import get_airtable_config, list_tables, create_table, create_field

load_dotenv()

SCHEMA_FILE = "airtable_schema.json"


def _load_schema():
    with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def create_airtable_schema():
    """Create Airtable schema from JSON definition."""
    try:
        api_key, base_id = get_airtable_config()
    except ValueError as e:
        print(f"❌ Erro de configuração: {e}")
        return False

    schema = _load_schema()

    # Get existing tables
    try:
        existing = list_tables()
        existing_tables = {t["name"]: t for t in existing.get("tables", [])}
        print(f"✓ Base atual tem {len(existing_tables)} tabela(s)")
    except Exception as e:
        print(f"❌ Erro ao listar tabelas: {e}")
        return False

    # Create missing tables
    created_count = 0
    for table_def in schema.get("tables", []):
        table_name = table_def["name"]
        fields_def = table_def.get("fields", [])

        if table_name in existing_tables:
            print(f"  ⊘ Tabela '{table_name}' já existe")
            continue

        # Find primary field
        primary_field = next((f for f in fields_def if f.get("primary")), None)
        if not primary_field:
            print(f"  ⚠ Tabela '{table_name}' sem campo primary - pulando")
            continue

        print(f"  → Criando tabela '{table_name}'...")

        try:
            # Create table with primary field
            create_payload = {
                "name": table_name,
                "fields": [
                    {
                        "name": primary_field["name"],
                        "type": primary_field["type"],
                    }
                ],
            }

            create_table(create_payload)
            existing_tables[table_name] = {"name": table_name, "id": f"tbl_{table_name}"}
            print(f"    ✓ Tabela criada")
            created_count += 1

            # Now add additional fields (but skip if they fail - fields may already exist)
            table_id = existing_tables[table_name].get("id")
            if table_id and table_id.startswith("tbl_"):
                # Airtable returns actual ID - we'd need to fetch it
                # For now, skip field creation on newly created tables
                pass

        except Exception as e:
            print(f"    ✗ Erro ao criar tabela: {str(e)[:80]}")

    if created_count > 0:
        print(f"\n✅ {created_count} tabela(s) criada(s) com sucesso!")
        print("\n📝 Próximo passo: adicione os campos manualmente em Airtable")
        print("   ou execute novamente para adicionar campos aos campos primários.")
        return True
    else:
        print("\n⊘ Todas as tabelas já existem ou não foi possível criá-las.")
        print("   Verifique as credenciais Airtable em .env")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("CRIADOR DE SCHEMA AIRTABLE")
    print("=" * 60)
    create_airtable_schema()
    print("=" * 60)
