#!/usr/bin/env python3
"""Teste de geração de ticket e upload para Cloudinary"""

import sys
import os
from dotenv import load_dotenv
import stripe

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

# Setup Stripe
stripe.api_key = os.getenv("STRIPE_API_KEY")

print("=" * 60)
print("Buscando charge para testar...")
print("=" * 60)

# Get a succeeded charge
charges = stripe.Charge.list(limit=5)

if charges.data:
    for charge in charges.data:
        charge_id = charge.id
        status = charge.status
        print(f"\nCharge: {charge_id} | Status: {status}")
        
        if status == 'succeeded':
            print(f"Testing ticket generation with Cloudinary upload...\n")
            
            from stripe_airtable_sync import generate_ticket_for_charge
            
            try:
                result = generate_ticket_for_charge(charge_id, auto_retrieve=False)
                print(f"\nResult: {result}")
                break
            except Exception as e:
                print(f"Error: {e}")
                import traceback
                traceback.print_exc()
else:
    print("No charges found")
