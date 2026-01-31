#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Add fields to Airtable tables via API.
Handles field creation for each table created by create_airtable_schema_simple.py
"""

import os
import requests
from dotenv import load_dotenv
from airtable_client import get_airtable_config

load_dotenv()

# ⚠️ NUNCA usar fallback hardcoded! Sempre buscar do .env com validação
API_KEY, BASE_ID = get_airtable_config()

HEADERS = {"Authorization": f"Bearer {API_KEY}"}

# Field configurations for each table
FIELDS_CONFIG = {
    "Charges": [
        {"name": "charge_id", "type": "singleLineText"},
        {"name": "amount", "type": "number"},
        {"name": "currency", "type": "singleLineText"},
        {"name": "status", "type": "singleLineText"},
        {"name": "customer", "type": "singleLineText"},
        {"name": "description", "type": "singleLineText"},
        {"name": "created", "type": "number"},
        {"name": "paid", "type": "checkbox"},
        {"name": "metadata", "type": "singleLineText"},
    ],
    "Payment_Intents": [
        {"name": "payment_intent_id", "type": "singleLineText"},
        {"name": "amount", "type": "number"},
        {"name": "currency", "type": "singleLineText"},
        {"name": "status", "type": "singleLineText"},
        {"name": "customer", "type": "singleLineText"},
        {"name": "created", "type": "number"},
    ],
    "Checkout_Sessions": [
        {"name": "session_id", "type": "singleLineText"},
        {"name": "customer_email", "type": "email"},
        {"name": "amount_total", "type": "number"},
        {"name": "currency", "type": "singleLineText"},
        {"name": "payment_status", "type": "singleLineText"},
        {"name": "fulfillment_status", "type": "singleLineText"},
        {"name": "created", "type": "number"},
        {"name": "expires_at", "type": "number"},
    ],
    "Customers": [
        {"name": "customer_id", "type": "singleLineText"},
        {"name": "email", "type": "email"},
        {"name": "name", "type": "singleLineText"},
        {"name": "phone", "type": "singleLineText"},
        {"name": "created", "type": "number"},
        {"name": "metadata", "type": "singleLineText"},
    ],
    "Payouts": [
        {"name": "payout_id", "type": "singleLineText"},
        {"name": "amount", "type": "number"},
        {"name": "currency", "type": "singleLineText"},
        {"name": "status", "type": "singleLineText"},
        {"name": "arrival_date", "type": "number"},
        {"name": "type", "type": "singleLineText"},
    ],
    "Tickets": [
        {"name": "ticket_id", "type": "singleLineText"},
        {"name": "charge_id", "type": "singleLineText"},
        {"name": "customer_email", "type": "email"},
        {"name": "event_name", "type": "singleLineText"},
        {"name": "event_date", "type": "date"},
        {"name": "pdf_base64", "type": "multilineText"},
        {"name": "qr_code", "type": "singleLineText"},
        {"name": "validated", "type": "checkbox"},
        {"name": "validation_date", "type": "date"},
        {"name": "created", "type": "number"},
    ],
    "QRCodes": [
        {"name": "qr_id", "type": "singleLineText"},
        {"name": "ticket_id", "type": "singleLineText"},
        {"name": "qr_data", "type": "singleLineText"},
        {"name": "validated", "type": "checkbox"},
        {"name": "validation_timestamp", "type": "number"},
        {"name": "validation_location", "type": "singleLineText"},
    ],
    "Logs": [
        {"name": "timestamp", "type": "number"},
        {"name": "log_type", "type": "singleLineText"},
        {"name": "entity_type", "type": "singleLineText"},
        {"name": "entity_id", "type": "singleLineText"},
        {"name": "action", "type": "singleLineText"},
        {"name": "status", "type": "singleLineText"},
        {"name": "message", "type": "multilineText"},
        {"name": "details", "type": "multilineText"},
    ],
}

def get_table_id(table_name):
    """Get table ID by name."""
    api_url = f"https://api.airtable.com/v0/meta/bases/{BASE_ID}/tables"
    response = requests.get(api_url, headers=HEADERS)
    if response.status_code != 200:
        print(f"[ERROR] Falha ao listar tabelas: {response.status_code} - {response.text}")
        return None
    
    tables = response.json().get("tables", [])
    for table in tables:
        if table.get("name") == table_name:
            return table.get("id")
    
    return None

def add_fields_to_table(table_name, fields):
    """Add fields to a table."""
    table_id = get_table_id(table_name)
    if not table_id:
        print(f"[ERROR] Tabela '{table_name}' não encontrada")
        return False
    
    print(f"\n📋 Adicionando campos à tabela '{table_name}'...")
    
    for field in fields:
        url = f"https://api.airtable.com/v0/bases/{BASE_ID}/tables/{table_id}/fields"
        data = {
            "name": field["name"],
            "type": field["type"]
        }
        
        response = requests.post(url, json=data, headers=HEADERS)
        
        if response.status_code in [200, 201]:
            print(f"  ✓ Campo '{field['name']}' criado")
        elif response.status_code == 422:
            # Field might already exist, skip
            print(f"  ⚠️  Campo '{field['name']}' já existe ou erro de validação")
        else:
            print(f"  ✗ Erro ao criar campo '{field['name']}': {response.status_code}")
            print(f"     Resposta: {response.text}")
    
    return True

def main():
    print("=" * 60)
    print("ADICIONANDO CAMPOS ÀS TABELAS AIRTABLE")
    print("=" * 60)
    
    if not API_KEY:
        print("[ERROR] AIRTABLE_API_KEY não configurada")
        return
    
    for table_name, fields in FIELDS_CONFIG.items():
        add_fields_to_table(table_name, fields)
    
    print("\n" + "=" * 60)
    print("Processo concluído!")
    print("=" * 60)

if __name__ == "__main__":
    main()
