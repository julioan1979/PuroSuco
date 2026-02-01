#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verifica se tickets têm charge_id preenchido"""

import sys
import os
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

from airtable_client import _headers, _table_url, get_airtable_config
import requests

api_key, base_id = get_airtable_config()

print("=" * 60)
print("Verificando tickets e seus charge_ids")
print("=" * 60)

url = _table_url(base_id, "Tickets")
params = {"pageSize": 10}

resp = requests.get(url, headers=_headers(api_key), params=params)
records = resp.json().get("records", [])

print(f"\nTotal recuperados: {len(records)}\n")

for idx, record in enumerate(records, 1):
    fields = record.get("fields", {})
    ticket_id = fields.get("ticket_id", "?")[:12]
    charge_id = fields.get("charge_id", "VAZIO")
    pdf_url = fields.get("pdf_url", "")
    
    status_charge = "OK" if charge_id and charge_id != "VAZIO" else "VAZIO"
    status_pdf = "OK" if pdf_url else "SEM PDF"
    
    print(f"[{idx}] Ticket: {ticket_id}...")
    print(f"     charge_id: {charge_id[:30] if charge_id and charge_id != 'VAZIO' else 'VAZIO'} [{status_charge}]")
    print(f"     pdf_url: {pdf_url[:50] if pdf_url else 'VAZIO'} [{status_pdf}]")
    print()

print("=" * 60)
