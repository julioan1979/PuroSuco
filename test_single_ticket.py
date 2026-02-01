#!/usr/bin/env python3
"""Teste de upload de PDF real para Cloudinary"""

import sys
import os
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from airtable_client import get_airtable_records

load_dotenv()

print("=" * 60)
print("🔍 Buscando charges para testar...")
print("=" * 60)

# Get charges
records = get_airtable_records(table="Charges", max_records=3)

if records:
    for record in records:
        fields = record.get('fields', {})
        charge_id = fields.get('charge_id', '?')
        status = fields.get('status', '?')
        print(f"\n📋 Charge: {charge_id[:30]}... | Status: {status}")
        
        if status == 'succeeded':
            print(f"   Testing ticket generation...\n")
            
            from stripe_airtable_sync import generate_ticket_for_charge
            
            try:
                result = generate_ticket_for_charge(charge_id, auto_retrieve=False)
                print(f"   Result: {result}")
            except Exception as e:
                print(f"   ❌ Error: {e}")
                import traceback
                traceback.print_exc()
else:
    print("❌ No charges found")
