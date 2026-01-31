#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Debug: List all tables in Airtable base
"""

import os
import requests
from dotenv import load_dotenv
from airtable_client import get_airtable_config

load_dotenv()

# ⚠️ NUNCA usar fallback hardcoded! Sempre buscar do .env com validação
API_KEY, BASE_ID = get_airtable_config()

HEADERS = {"Authorization": f"Bearer {API_KEY}"}

def list_tables():
    """List all tables in the base."""
    api_url = f"https://api.airtable.com/v0/meta/bases/{BASE_ID}/tables"
    print(f"URL: {api_url}")
    print(f"API Key: {API_KEY[:10]}...")
    
    response = requests.get(api_url, headers=HEADERS)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 200:
        tables = response.json().get("tables", [])
        print(f"\n✓ {len(tables)} tabelas encontradas:")
        for table in tables:
            print(f"  - {table.get('name')} (ID: {table.get('id')})")

if __name__ == "__main__":
    list_tables()
