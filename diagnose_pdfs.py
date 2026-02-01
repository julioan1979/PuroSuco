"""
DIAGNÓSTICO E CORREÇÃO: Bilhetes sem PDFs
Verifica tickets existentes e regenera PDFs faltantes
"""
import os
import sys
import requests
from dotenv import load_dotenv
from qrcode_manager import get_ticket_by_charge_id
from airtable_client import get_airtable_config
from stripe_airtable_sync import _generate_and_store_ticket_from_charge
import stripe

# Fix encoding for Windows console
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

load_dotenv()
stripe.api_key = os.getenv("STRIPE_API_KEY")

print("\n" + "="*60)
print("DIAGNOSTICO: Bilhetes sem PDFs")
print("="*60 + "\n")

api_key, base_id = get_airtable_config()

# Get all tickets
print("📋 Recuperando todos os tickets da base...")
url = f"https://api.airtable.com/v0/{base_id}/Tickets"
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

resp = requests.get(url, headers=headers, params={"maxRecords": 100}, timeout=30)
tickets = resp.json().get("records", [])

print(f"✅ Encontrados {len(tickets)} tickets\n")

# Check which ones have PDFs
tickets_without_pdf = []
for ticket in tickets:
    fields = ticket.get("fields", {})
    ticket_id = fields.get("ticket_id")
    charge_id = fields.get("charge_id")
    pdf_attachment = fields.get("pdf_attachment", [])
    
    status = "❌ SEM PDF" if not pdf_attachment else "✅ COM PDF"
    print(f"{status} | Ticket: {ticket_id[:8]}... | Charge: {charge_id}")
    
    if not pdf_attachment:
        tickets_without_pdf.append({
            "ticket_id": ticket_id,
            "charge_id": charge_id,
            "airtable_id": ticket.get("id")
        })

print(f"\n📊 RESUMO:")
print(f"   Total de tickets: {len(tickets)}")
print(f"   Com PDF: {len(tickets) - len(tickets_without_pdf)}")
print(f"   Sem PDF: {len(tickets_without_pdf)}\n")

if not tickets_without_pdf:
    print("✅ Todos os bilhetes têm PDFs! Nada a fazer.")
else:
    print(f"🔧 Regenerando {len(tickets_without_pdf)} PDFs...\n")
    
    for ticket in tickets_without_pdf:
        charge_id = ticket["charge_id"]
        ticket_id = ticket["ticket_id"]
        
        try:
            # Get charge from Stripe
            print(f"📍 Processando: {ticket_id[:8]}...")
            charge = stripe.Charge.retrieve(charge_id, expand=["customer"])
            
            # Regenerate and upload PDF
            from stripe_airtable_sync import _generate_and_store_ticket_from_charge
            if _generate_and_store_ticket_from_charge(charge):
                print(f"   ✅ PDF regenerado e enviado")
            else:
                print(f"   ⚠️ Falha ao gerar PDF")
        except Exception as e:
            print(f"   ❌ Erro: {str(e)}")

print("\n" + "="*60)
print("✅ Diagnóstico completo!")
print("="*60 + "\n")
