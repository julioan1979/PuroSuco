"""
Remove old pdf_data field from Tickets table (cleanup)
"""
import os
import requests
from dotenv import load_dotenv
from airtable_client import get_airtable_config, list_tables

load_dotenv()
api_key, base_id = get_airtable_config()

print("\n🧹 LIMPEZA - Remover campo pdf_data antigo")
print("=" * 60)

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

# Get Tickets table
base_info = list_tables()
tickets_table = None
for table in base_info.get("tables", []):
    if table["name"] == "Tickets":
        tickets_table = table
        break

if not tickets_table:
    print("❌ Tabela Tickets não encontrada!")
    exit(1)

table_id = tickets_table["id"]
print(f"📋 Tabela: {table_id}\n")

# Find pdf_data field
pdf_data_field = None
for field in tickets_table.get("fields", []):
    if field["name"] == "pdf_data":
        pdf_data_field = field
        break

if not pdf_data_field:
    print("✅ Campo pdf_data não existe mais")
    exit(0)

print(f"🔍 Campo encontrado:")
print(f"   Nome: {pdf_data_field['name']}")
print(f"   ID: {pdf_data_field['id']}")
print(f"   Tipo: {pdf_data_field.get('type')}\n")

# Delete field
print("🗑️ Deletando campo...")
delete_url = f"https://api.airtable.com/v0/meta/bases/{base_id}/tables/{table_id}/fields/{pdf_data_field['id']}"

resp = requests.delete(delete_url, headers=headers, timeout=30)

if resp.status_code in [200, 204]:
    print("✅ Campo pdf_data deletado com sucesso!\n")
    print("=" * 60)
    print("✅ Limpeza concluída - Schema atualizado!")
    print("=" * 60)
else:
    print(f"❌ Erro: {resp.status_code}")
    print(f"Resposta: {resp.text}\n")
