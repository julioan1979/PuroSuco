#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regenera PDFs para tickets sem pdf_url e faz upload para Cloudinary"""

import sys
import os
from dotenv import load_dotenv
import stripe

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

from airtable_client import _headers, _table_url, get_airtable_config
from stripe_airtable_sync import _generate_and_store_ticket_from_charge
import requests

# Configure Stripe
stripe.api_key = os.getenv("STRIPE_API_KEY")

print("=" * 60)
print("Regenerando PDFs para tickets sem pdf_url")
print("=" * 60)

api_key, base_id = get_airtable_config()
url = _table_url(base_id, "Tickets")
headers = _headers(api_key)

# Get all tickets without pdf_url
print("\nBuscando tickets sem pdf_url...")
params = {
    "filterByFormula": "OR({pdf_url} = '', {pdf_url} = BLANK())",
    "pageSize": 100
}

all_tickets = []
offset = None

while True:
    if offset:
        params["offset"] = offset
    
    resp = requests.get(url, headers=headers, params=params)
    data = resp.json()
    
    records = data.get("records", [])
    all_tickets.extend(records)
    
    offset = data.get("offset")
    if not offset:
        break

print(f"Encontrados {len(all_tickets)} tickets sem pdf_url")

if not all_tickets:
    print("\nTodos os tickets ja tem pdf_url!")
    exit(0)

print(f"\nRegenerando PDFs para {len(all_tickets)} tickets...\n")

success_count = 0
error_count = 0

for idx, ticket_record in enumerate(all_tickets, 1):
    fields = ticket_record.get("fields", {})
    charge_id = fields.get("charge_id")
    ticket_id = fields.get("ticket_id", "?")[:12]
    
    if not charge_id:
        print(f"[{idx}/{len(all_tickets)}] SKIP {ticket_id}... - Sem charge_id")
        continue
    
    print(f"[{idx}/{len(all_tickets)}] Processando {ticket_id}... | Charge: {charge_id[:20]}...")
    
    try:
        # Fetch charge from Stripe
        charge = stripe.Charge.retrieve(charge_id)
        
        # Regenerate ticket with PDF upload to Cloudinary
        result = _generate_and_store_ticket_from_charge(charge)
        
        if result:
            success_count += 1
            print(f"              OK - PDF uploaded to Cloudinary")
        else:
            error_count += 1
            print(f"              ERRO - Falha na geracao")
    
    except stripe.error.StripeError as e:
        error_count += 1
        print(f"              ERRO Stripe: {str(e)[:80]}")
    except Exception as e:
        error_count += 1
        print(f"              ERRO: {str(e)[:80]}")

print(f"\n{'=' * 60}")
print(f"RESUMO:")
print(f"  Total processados: {len(all_tickets)}")
print(f"  Sucesso: {success_count}")
print(f"  Erros: {error_count}")
print(f"{'=' * 60}")
