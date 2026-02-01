#!/usr/bin/env python3
"""Diagnóstico: Bilhetes sem PDFs - Tenta regenerar e upload para Cloudinary"""

import sys
import os
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from stripe_airtable_sync import (
    _generate_and_store_ticket_from_charge,
    get_all_charges,
    get_ticket_by_charge_id
)

load_dotenv()

print("=" * 60)
print("🔍 DIAGNÓSTICO: Bilhetes sem PDFs (Cloudinary)")
print("=" * 60)

# Get all charges
charges = get_all_charges()
print(f"\n📋 Recuperando todos os charges...")
print(f"✅ Encontrados {len(charges)} charges")

# Collect tickets without PDF
tickets_without_pdf = []

for charge in charges:
    charge_id = charge.get('id')
    status = charge.get('status')
    
    # Only process succeeded charges
    if status != 'succeeded':
        continue
    
    # Check if ticket exists
    ticket_result = get_ticket_by_charge_id(charge_id)
    
    if not ticket_result.get('success'):
        # No ticket yet
        print(f"\n🔴 SEM TICKET | Charge: {charge_id[:20]}...")
        tickets_without_pdf.append((charge_id, charge))
    else:
        ticket_id = ticket_result.get('ticket_id')
        # Check if has PDF URL
        # For now, regenerate for testing
        print(f"\n⚪ COM TICKET | Charge: {charge_id[:20]}...")
        tickets_without_pdf.append((charge_id, charge))

print(f"\n\n📊 RESUMO:")
print(f"   Total de charges succeeded: {len(charges)}")
print(f"   Para processar: {len(tickets_without_pdf)}")

if tickets_without_pdf:
    print(f"\n🔧 Regenerando primeiros 3 PDFs...\n")
    
    for i, (charge_id, charge) in enumerate(tickets_without_pdf[:3]):
        print(f"\n📍 Processando: {charge_id[:20]}...")
        try:
            result = _generate_and_store_ticket_from_charge(charge)
            if result.get('success'):
                print(f"   ✅ PDF regenerado e enviado para Cloudinary")
            else:
                print(f"   ❌ Erro: {result.get('error')}")
        except Exception as e:
            print(f"   ❌ Exception: {str(e)[:100]}")
            import traceback
            traceback.print_exc()

print(f"\n\n{'=' * 60}")
print(f"✅ Diagnóstico completo!")
print(f"{'=' * 60}")
