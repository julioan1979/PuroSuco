#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Simula o auto-sync que acontece ao carregar a página do app"""

import sys
import os
from dotenv import load_dotenv
import stripe

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

from stripe_airtable_sync import sync_charge_to_airtable, _generate_and_store_ticket_from_charge
from qrcode_manager import get_ticket_by_charge_id
from airtable_client import _headers, _table_url, get_airtable_config
import requests

# Configure Stripe
stripe.api_key = os.getenv("STRIPE_API_KEY")

print("=" * 60)
print("SIMULACAO: Auto-sync ao recarregar pagina")
print("=" * 60)

# Get charges (igual ao app)
charges_obj = stripe.Charge.list(limit=50, expand=["data.customer"])
charges = list(charges_obj.data)

print(f"\nTotal de charges: {len(charges)}")

sync_count = 0
ticket_count = 0
errors = 0

for idx, ch in enumerate(charges[:5], 1):  # Processar apenas 5 para teste
    charge_id = ch.get('id')
    status = ch.get('status')
    
    print(f"\n[{idx}/5] Charge: {charge_id[:25]}... | Status: {status}")
    
    try:
        # SEMPRE sincronizar charge
        sync_charge_to_airtable(ch, auto_generate_ticket=False)
        sync_count += 1
        print(f"       Charge sincronizado")
        
        # SEMPRE verificar se tem ticket E se tem pdf_url
        if ch.get("status") == "succeeded":
            existing_ticket = get_ticket_by_charge_id(ch.get("id"))
            needs_pdf = False
            
            if not existing_ticket.get("success"):
                # Não tem ticket, gerar
                print(f"       Ticket NAO existe - precisa gerar")
                needs_pdf = True
            else:
                # Tem ticket, verificar se tem pdf_url
                ticket_id = existing_ticket.get("ticket_id")
                print(f"       Ticket existe: {ticket_id[:12]}...")
                
                api_key, base_id = get_airtable_config()
                url = _table_url(base_id, "Tickets")
                params = {"filterByFormula": f"{{ticket_id}}='{ticket_id}'"}
                resp = requests.get(url, headers=_headers(api_key), params=params)
                records = resp.json().get("records", [])
                
                if records and not records[0].get("fields", {}).get("pdf_url"):
                    print(f"       Ticket SEM pdf_url - precisa gerar")
                    needs_pdf = True
                else:
                    print(f"       Ticket COM pdf_url - OK")
            
            if needs_pdf:
                # Gerar/atualizar ticket com PDF no Cloudinary
                print(f"       Gerando PDF...")
                try:
                    if _generate_and_store_ticket_from_charge(ch):
                        ticket_count += 1
                        print(f"       PDF gerado com sucesso!")
                except Exception as pdf_err:
                    errors += 1
                    print(f"       ERRO ao gerar PDF: {str(pdf_err)[:80]}")
                    import traceback
                    traceback.print_exc()
    except Exception as e:
        errors += 1
        print(f"       ERRO geral: {str(e)[:80]}")
        import traceback
        traceback.print_exc()

print(f"\n{'=' * 60}")
print(f"RESUMO:")
print(f"  Charges sincronizados: {sync_count}")
print(f"  PDFs gerados: {ticket_count}")
print(f"  Erros: {errors}")
print(f"{'=' * 60}")
