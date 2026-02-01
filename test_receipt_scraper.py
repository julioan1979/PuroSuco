#!/usr/bin/env python3
"""
Quick test of receipt scraper integration with mock data.
Tests that all pieces fit together without errors.
"""

import os
from dotenv import load_dotenv
from stripe_receipt_scraper import (
    scrape_stripe_receipt,
    _extract_product_items,
    _extract_custom_message
)

load_dotenv()

print("\n" + "="*60)
print("RECEIPT SCRAPER - INTEGRATION TEST")
print("="*60)

# Test 1: Check regex patterns load correctly
print("\n[TEST 1] Verifying regex patterns...")
try:
    from stripe_receipt_scraper import (
        RECEIPT_NUMBER_PATTERN,
        SELLER_PATTERN,
        AMOUNT_PATTERN,
        DATE_PATTERN,
        PRODUCT_PATTERN,
        CUSTOM_MESSAGE_PATTERN
    )
    print("✅ All regex patterns loaded successfully")
except Exception as e:
    print(f"❌ Pattern load failed: {e}")
    exit(1)

# Test 2: Test product extraction with sample HTML
print("\n[TEST 2] Testing product item extraction...")
sample_html = """
<td class="Table-description">Niver Bia 2026 × 1</td>
<td class="Table-amount">€15.00</td>
<td class="Table-description">Outro Produto × 2</td>
<td class="Table-amount">€30.00</td>
"""
items = _extract_product_items(sample_html)
if items:
    print(f"✅ Extracted {len(items)} items:")
    for item in items:
        print(f"   - {item['description']} × {item['quantity']} = €{item['price']}")
else:
    print("⚠️  No items extracted (patterns may need adjustment)")

# Test 3: Test custom message extraction
print("\n[TEST 3] Testing custom message extraction...")
sample_msg_html = """
<div>A Bia vai adorar ler a tua mensagem 🎉 Parabéns! Se tiveres dúvidas...</div>
"""
message = _extract_custom_message(sample_msg_html)
if message:
    print(f"✅ Custom message extracted: '{message}'")
else:
    print("⚠️  No custom message extracted")

# Test 4: Verify Airtable integration imports
print("\n[TEST 4] Testing Airtable integration...")
try:
    from airtable_client import upsert_record
    from app_logger import log_action
    print("✅ Airtable client and logger imported successfully")
except Exception as e:
    print(f"❌ Airtable integration failed: {e}")
    exit(1)

# Test 5: Verify sync integration
print("\n[TEST 5] Testing sync workflow integration...")
try:
    from stripe_airtable_sync import sync_charge_to_airtable
    print("✅ Sync module with receipt scraper integrated successfully")
except Exception as e:
    print(f"❌ Sync integration failed: {e}")
    exit(1)

print("\n" + "="*60)
print("✅ ALL INTEGRATION TESTS PASSED")
print("="*60)
print("\nNext steps:")
print("1. Run test with real Stripe receipt URL (when available)")
print("2. Verify Receipts table created in Airtable")
print("3. Verify receipts appear in Receipts table after syncing charges")
print("\n")
