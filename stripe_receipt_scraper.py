"""
Stripe Receipt HTML Scraper
Extracts receipt data (items, dates, amounts, custom messages) from Stripe receipt URLs
and stores in Airtable Receipts table.
"""

import re
import json
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any

import requests
from bs4 import BeautifulSoup
from app_logger import log_action
from airtable_client import upsert_record

# =========================================================
# REGEX PATTERNS
# =========================================================

RECEIPT_NUMBER_PATTERN = re.compile(r"Receipt\s*#([\d-]+)")
SELLER_PATTERN = re.compile(r"Receipt from\s+([^<\n]+)")
AMOUNT_PATTERN = re.compile(r"AMOUNT PAID[^€]*€([\d,\.]+)")
DATE_PATTERN = re.compile(r"DATE PAID[^A-Z]*([A-Z][a-z]+\s+\d+,\s+\d{4}.*?[AP]M)")
PRODUCT_PATTERN = re.compile(r"([^×<>\n]+?)\s*×\s*(\d+)[^€]*€([\d,\.]+)")
CUSTOM_MESSAGE_PATTERN = re.compile(
    r"A Bia vai adorar ler a tua mensagem\s+(.+?)(?=If you have|$)",
    re.DOTALL | re.IGNORECASE
)

# =========================================================
# CORE SCRAPER FUNCTIONS
# =========================================================


def scrape_stripe_receipt(receipt_url: str, charge_id: str) -> Optional[Dict[str, Any]]:
    """
    Scrape Stripe receipt HTML and extract structured data.
    
    Args:
        receipt_url: Full URL to Stripe receipt (e.g., https://pay.stripe.com/receipts/payment/[token])
        charge_id: Stripe charge ID (for linking in Airtable)
    
    Returns:
        Dict with extracted fields or None if scraping failed:
        {
            "receipt_id": "unique_id",
            "charge_id": "ch_xxx",
            "receipt_url": "https://...",
            "receipt_number": "12345-67890",
            "seller_name": "Business Name",
            "amount_paid": 15.00,
            "currency": "EUR",
            "product_items": [{"description": "...", "quantity": 1, "price": 15.00}, ...],
            "custom_message": "Optional message text",
            "items_count": 1,
            "scraped_at": "2026-02-01T10:30:00Z",
            "scrape_status": "success"
        }
    """
    if not receipt_url:
        return None
    
    try:
        # Fetch receipt HTML
        resp = requests.get(receipt_url, timeout=10)
        if resp.status_code != 200:
            log_action("receipt_scraper", "fetch", "error", 
                      error_details=f"HTTP {resp.status_code} for {receipt_url}")
            return None
        
        html = resp.text
        soup = BeautifulSoup(html, "lxml")
        
        # Extract receipt ID from URL (token after last /)
        receipt_id = receipt_url.split("/")[-1] if receipt_url else charge_id
        
        # Extract receipt number
        receipt_number = None
        match = RECEIPT_NUMBER_PATTERN.search(html)
        if match:
            receipt_number = match.group(1)
        
        # Extract seller name
        seller_name = None
        match = SELLER_PATTERN.search(html)
        if match:
            seller_name = match.group(1).strip()
        
        # Extract amount paid
        amount_paid = None
        match = AMOUNT_PATTERN.search(html)
        if match:
            amount_str = match.group(1).replace(",", ".")
            try:
                amount_paid = float(amount_str)
            except ValueError:
                pass
        
        # Extract currency (default EUR)
        currency = "EUR"
        if "USD" in html or "$" in html[:500]:
            currency = "USD"
        
        # Extract product items
        product_items = _extract_product_items(html)
        items_count = len(product_items)
        
        # Extract custom message
        custom_message = _extract_custom_message(html)
        
        # Build result
        result = {
            "receipt_id": receipt_id,
            "charge_id": charge_id,
            "receipt_url": receipt_url,
            "receipt_number": receipt_number,
            "seller_name": seller_name,
            "amount_paid": amount_paid,
            "currency": currency,
            "product_items": product_items,  # Will be stringified in Airtable
            "custom_message": custom_message,
            "items_count": items_count,
            "scraped_at": datetime.now(tz=timezone.utc).isoformat(),
            "scrape_status": "success"
        }
        
        log_action("receipt_scraper", "scrape", "success",
                  message=f"Scraped receipt {receipt_id}: {items_count} items, {seller_name}")
        
        return result
        
    except requests.RequestException as e:
        log_action("receipt_scraper", "scrape", "error",
                  error_details=f"Request failed: {str(e)}")
        return None
    except Exception as e:
        log_action("receipt_scraper", "scrape", "error",
                  error_details=f"Parsing failed: {str(e)}")
        return None


def _extract_product_items(html: str) -> List[Dict[str, Any]]:
    """Extract product items from receipt HTML."""
    items = []
    
    try:
        # Use regex to find all product lines (handles Stripe's HTML structure)
        for match in PRODUCT_PATTERN.finditer(html):
            description = match.group(1).strip()
            quantity = int(match.group(2))
            price_str = match.group(3).replace(",", ".")
            
            try:
                price = float(price_str)
            except ValueError:
                price = 0.0
            
            # Filter out common non-product lines
            desc_lower = description.lower()
            if any(x in desc_lower for x in ["subtotal", "total", "tax", "fee", "discount"]):
                continue
            
            items.append({
                "description": description,
                "quantity": quantity,
                "price": price
            })
        
    except Exception as e:
        log_action("receipt_scraper", "extract_items", "error",
                  error_details=f"Item extraction failed: {str(e)}")
    
    return items


def _extract_custom_message(html: str) -> Optional[str]:
    """Extract custom personalized message after the marker phrase."""
    try:
        match = CUSTOM_MESSAGE_PATTERN.search(html)
        if match:
            message = match.group(1).strip()
            # Clean up HTML tags and extra whitespace
            message = re.sub(r"<[^>]+>", "", message)
            message = re.sub(r"\s+", " ", message).strip()
            
            if message and len(message) > 5:  # Only return if meaningful
                return message
    except Exception as e:
        log_action("receipt_scraper", "extract_message", "error",
                  error_details=f"Message extraction failed: {str(e)}")
    
    return None


# =========================================================
# AIRTABLE INTEGRATION
# =========================================================


def scrape_and_store_receipt(receipt_url: str, charge_id: str) -> bool:
    """
    Scrape receipt and upsert to Airtable Receipts table.
    
    Args:
        receipt_url: Stripe receipt URL
        charge_id: Stripe charge ID (merge key)
    
    Returns:
        True if successful, False otherwise
    """
    if not receipt_url or not charge_id:
        return False
    
    try:
        # Scrape receipt
        receipt_data = scrape_stripe_receipt(receipt_url, charge_id)
        if not receipt_data:
            log_action("receipt_scraper", "store", "error",
                      error_details="Scraping returned None")
            return False
        
        # Convert product items to JSON string for storage
        receipt_data["product_items"] = json.dumps(receipt_data["product_items"], ensure_ascii=False)
        
        # Upsert to Receipts table
        upsert_record(
            "Receipts",
            receipt_data,
            merge_on="charge_id"
        )
        
        log_action("receipt_scraper", "store", "success",
                  message=f"Receipt {receipt_data['receipt_id']} stored for charge {charge_id}")
        return True
        
    except Exception as e:
        log_action("receipt_scraper", "store", "error",
                  error_details=f"Upsert failed: {str(e)}")
        return False


def scrape_receipts_from_charges(charges: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Batch process receipts from multiple charges.
    
    Args:
        charges: List of Stripe charge objects from API
    
    Returns:
        Stats dict: {"processed": int, "successful": int, "failed": int, "skipped": int}
    """
    stats = {"processed": 0, "successful": 0, "failed": 0, "skipped": 0}
    
    for charge in charges:
        charge_id = charge.get("id")
        receipt_url = charge.get("receipt_url")
        
        if not receipt_url:
            stats["skipped"] += 1
            continue
        
        stats["processed"] += 1
        if scrape_and_store_receipt(receipt_url, charge_id):
            stats["successful"] += 1
        else:
            stats["failed"] += 1
    
    log_action("receipt_scraper", "batch", "success",
              message=f"Batch processed: {stats['processed']} charges, {stats['successful']} successful, {stats['failed']} failed")
    
    return stats


if __name__ == "__main__":
    # Test: Scrape a single receipt (for manual testing)
    print("Receipt Scraper Module")
    print("Import this module and call scrape_and_store_receipt(url, charge_id)")
