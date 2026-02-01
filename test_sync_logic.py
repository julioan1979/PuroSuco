#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Teste da lógica de sincronização - verificar se detecta tickets sem pdf_url"""

import sys
import os
from dotenv import load_dotenv
import stripe

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

from qrcode_manager import get_ticket_by_charge_id
from airtable_client import _headers, _table_url, get_airtable_config, upsert_record
import requests

# Configure Stripe
stripe.api_key = os.getenv("STRIPE_API_KEY")

print("=" * 60)
print("Teste: Deteccao de tickets sem pdf_url")
print("=" * 60)

# Get a charge
charges = stripe.Charge.list(limit=5, expand=["data.customer"])

if not charges.data:
    print("Nenhum charge encontrado!")
    exit(1)

# Pegar primeiro charge succeeded
test_charge = None
for ch in charges.data:
    if ch.status == "succeeded":
        test_charge = ch
        break

if not test_charge:
    print("Nenhum charge succeeded encontrado!")
    exit(1)

charge_id = test_charge.id
print(f"\nCharge de teste: {charge_id}")

# Verificar se tem ticket
existing_ticket = get_ticket_by_charge_id(charge_id)

if not existing_ticket.get("success"):
    print(f"Ticket NAO existe - sera criado")
    needs_pdf = True
else:
    ticket_id = existing_ticket.get("ticket_id")
    print(f"Ticket existe: {ticket_id[:12]}...")
    
    # Verificar se tem pdf_url
    api_key, base_id = get_airtable_config()
    url = _table_url(base_id, "Tickets")
    params = {"filterByFormula": f"{{ticket_id}}='{ticket_id}'"}
    resp = requests.get(url, headers=_headers(api_key), params=params)
    records = resp.json().get("records", [])
    
    if records:
        fields = records[0].get("fields", {})
        pdf_url = fields.get("pdf_url")
        
        if pdf_url:
            print(f"  pdf_url: {pdf_url[:60]}...")
            print(f"  Status: JA TEM PDF - nao precisa gerar")
            needs_pdf = False
        else:
            print(f"  pdf_url: VAZIO")
            print(f"  Status: SEM PDF - precisa gerar")
            needs_pdf = True
    else:
        print(f"  Erro: Ticket nao encontrado no Airtable!")
        needs_pdf = True

print(f"\nDecisao: {'GERAR PDF' if needs_pdf else 'SKIP (ja tem)'}")

if needs_pdf:
    print("\nGerando PDF...")
    from stripe_airtable_sync import _generate_and_store_ticket_from_charge
    
    result = _generate_and_store_ticket_from_charge(test_charge)
    
    if result:
        print("SUCESSO: PDF gerado e enviado para Cloudinary!")
    else:
        print("ERRO: Falha na geracao do PDF")

print("\n" + "=" * 60)
