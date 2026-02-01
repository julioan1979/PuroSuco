#!/usr/bin/env python3
"""Verifica campos do Airtable e cria pdf_url se não existir"""

import os
from dotenv import load_dotenv
import requests

load_dotenv()

base_id = os.getenv('Airtable_Base_ID')
api_key = os.getenv('Airtable_API_Key')

# List existing fields in Tickets table
url = f'https://api.airtable.com/v0/meta/bases/{base_id}/tables'
headers = {'Authorization': f'Bearer {api_key}'}

resp = requests.get(url, headers=headers)
data = resp.json()

tickets_table = None
for table in data['tables']:
    if table['name'] == 'Tickets':
        tickets_table = table
        break

if not tickets_table:
    print("Tickets table not found!")
    exit(1)

print(f"\nExisting fields in Tickets table ({len(tickets_table['fields'])} fields):")
pdf_url_exists = False
for field in tickets_table['fields']:
    print(f"  {field['name']}: {field['type']}")
    if field['name'] == 'pdf_url':
        pdf_url_exists = True

if not pdf_url_exists:
    print("\nCreating pdf_url field...")
    create_url = f'https://api.airtable.com/v0/meta/bases/{base_id}/tables/{tickets_table["id"]}/fields'
    
    field_data = {
        "name": "pdf_url",
        "type": "url"
    }
    
    create_resp = requests.post(create_url, headers=headers, json=field_data)
    
    if create_resp.status_code == 200:
        print("SUCCESS: pdf_url field created!")
        print(f"Field: {create_resp.json()}")
    else:
        print(f"ERROR: {create_resp.status_code}")
        print(create_resp.text)
else:
    print("\npdf_url field already exists!")
