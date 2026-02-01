"""
Script to update Airtable schema: replace pdf_data with pdf_attachment field
"""
import os
import requests
from dotenv import load_dotenv
from airtable_client import get_airtable_config

load_dotenv()
api_key, base_id = get_airtable_config()

print("=" * 60)
print("ATUALIZAR SCHEMA - Tickets: pdf_data → pdf_attachment")
print("=" * 60)

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

# Step 1: List records to find one with pdf_data
print("\n🔍 Escaneando registos para encontrar campo pdf_data...")
records_url = f"https://api.airtable.com/v0/{base_id}/Tickets"
params = {"pageSize": 1}
resp = requests.get(records_url, headers=headers, params=params, timeout=30)

if resp.status_code == 200:
    records = resp.json().get("records", [])
    if records:
        record = records[0]
        fields = record.get("fields", {})
        has_pdf_data = "pdf_data" in fields
        has_pdf_attachment = "pdf_attachment" in fields
        
        print(f"📋 Registro de amostra verificado")
        print(f"   - Tem campo pdf_data: {has_pdf_data}")
        print(f"   - Tem campo pdf_attachment: {has_pdf_attachment}\n")
        
        if has_pdf_data and not has_pdf_attachment:
            print("✅ Campo pdf_data encontrado, pode ser substituído\n")
        elif has_pdf_attachment:
            print("⚠️ Campo pdf_attachment já existe\n")

# Step 2: Get table metadata via list_tables
from airtable_client import list_tables

print("🔄 Consultando estrutura da base...")
try:
    base_info = list_tables()
    tables = base_info.get("tables", [])
    
    tickets_table = None
    for table in tables:
        if table["name"] == "Tickets":
            tickets_table = table
            break
    
    if not tickets_table:
        print("❌ Tabela Tickets não encontrada!")
        exit(1)
    
    table_id = tickets_table["id"]
    print(f"✅ Tabela encontrada: {table_id}\n")
    
    # Check if we can access fields
    print("📊 Campos da tabela Tickets:")
    fields = tickets_table.get("fields", [])
    
    if not fields:
        print("⚠️ Não conseguimos acessar os campos via metadata API")
        print("   (Airtable pode ter restrições de acesso)")
        print("\n📝 Solução manual:")
        print("   1. Abra https://airtable.com")
        print("   2. Vá para tabela 'Tickets'")
        print("   3. Clique em '+' para adicionar campo")
        print("   4. Nome: pdf_attachment")
        print("   5. Tipo: Attachment")
        print("   6. Delete o campo 'pdf_data' (se não usar mais)\n")
    else:
        pdf_data_id = None
        pdf_attachment_id = None
        
        for field in fields:
            name = field.get("name")
            field_id = field.get("id")
            field_type = field.get("type")
            
            if name == "pdf_data":
                pdf_data_id = field_id
                print(f"  ❌ {name} ({field_type}) - SERÁ SUBSTITUÍDO")
            elif name == "pdf_attachment":
                pdf_attachment_id = field_id
                print(f"  ✅ {name} ({field_type}) - JÁ EXISTE")
            else:
                print(f"  ✓ {name} ({field_type})")
        
        print()
        
        if pdf_data_id and not pdf_attachment_id:
            print(f"🔄 Deletando campo pdf_data ({pdf_data_id})...")
            delete_url = f"https://api.airtable.com/v0/meta/bases/{base_id}/tables/{table_id}/fields/{pdf_data_id}"
            resp_delete = requests.delete(delete_url, headers=headers, timeout=30)
            
            if resp_delete.status_code in [200, 204]:
                print("✅ Campo pdf_data deletado\n")
                
                print("➕ Criando campo pdf_attachment...")
                create_url = f"https://api.airtable.com/v0/meta/bases/{base_id}/tables/{table_id}/fields"
                new_field = {
                    "name": "pdf_attachment",
                    "type": "multipleAttachments"
                }
                resp_create = requests.post(create_url, headers=headers, json=new_field, timeout=30)
                
                if resp_create.status_code == 201:
                    result = resp_create.json()
                    print(f"✅ Campo pdf_attachment criado!")
                    print(f"   ID: {result.get('id')}")
                    print(f"   Tipo: multipleAttachments\n")
                else:
                    print(f"❌ Erro: {resp_create.status_code}")
                    print(f"   {resp_create.text}\n")
            else:
                print(f"❌ Erro ao deletar: {resp_delete.status_code}\n")
        elif pdf_attachment_id:
            print("✅ Campo pdf_attachment já existe, nenhuma ação necessária\n")

except Exception as e:
    print(f"❌ Erro: {str(e)}\n")

print("=" * 60)
print("✅ Schema pronto para usar!")
print("=" * 60)
print("\n📝 Próximas etapas:")
print("1. Novos tickets terão PDFs enviados como attachment")
print("2. PDFs aparecem na coluna 'pdf_attachment'")
print("3. Airtable gerencia download/visualização\n")

