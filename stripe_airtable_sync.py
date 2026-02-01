import uuid
from datetime import datetime, timezone
from airtable_client import upsert_record
from app_logger import log_sync, log_pdf_generation
from pdf_generator import generate_ticket_pdf, generate_qrcode_data
from stripe_receipt_scraper import scrape_and_store_receipt
import stripe

stripe_key = None


def set_stripe_key(api_key: str):
    """Set Stripe API key for module."""
    global stripe_key
    stripe_key = api_key
    stripe.api_key = api_key


def _ts_to_iso(ts):
    if not ts:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def sync_charge_to_airtable(charge: dict, auto_generate_ticket=False) -> bool:
    """
    Synchronize Stripe charge to Airtable Charges table.
    Optionally generate a ticket PDF.
    
    Args:
        charge (dict): Stripe charge object
        auto_generate_ticket (bool): Gerar ticket PDF automaticamente
        
    Returns:
        bool: True se sucesso, False se erro
        
    Raises:
        Erros são capturados e registados no log
    """
    if not charge:
        log_sync("Charge", "unknown", "error", "Charge object is empty")
        return False
    
    charge_id = charge.get("id")
    if not charge_id:
        log_sync("Charge", "unknown", "error", "Charge ID is missing")
        return False
    
    try:
        fields = {
            "charge_id": charge_id,
            "created_at": _ts_to_iso(charge.get("created")),
            "status": charge.get("status"),
            "amount": (charge.get("amount") or 0) / 100,
            "currency": (charge.get("currency") or "").upper(),
            "customer_id": charge.get("customer"),
            "customer_email": (charge.get("billing_details") or {}).get("email"),
            "billing_name": (charge.get("billing_details") or {}).get("name"),
            "billing_phone": (charge.get("billing_details") or {}).get("phone"),
            "description": charge.get("description"),
            "invoice_id": charge.get("invoice"),
            "payment_intent_id": charge.get("payment_intent"),
            "receipt_url": charge.get("receipt_url"),
            "livemode": charge.get("livemode")
        }
        upsert_record("Charges", fields, merge_on="charge_id")
        log_sync("Charge", charge_id, "success", f"Charge {charge_id} sincronizado")

        # Scrape and store receipt if available
        receipt_url = charge.get("receipt_url")
        if receipt_url:
            try:
                if scrape_and_store_receipt(receipt_url, charge_id):
                    log_sync("Receipt", charge_id, "success", f"Receipt scraped for {charge_id}")
                else:
                    log_sync("Receipt", charge_id, "warning", f"Receipt scraping failed for {charge_id}")
            except Exception as receipt_err:
                log_sync("Receipt", charge_id, "warning", f"Receipt scraping exception: {str(receipt_err)}")
                # Não retornar False pois o charge foi sincronizado com sucesso

        # Generate ticket if enabled
        if auto_generate_ticket:
            try:
                _generate_and_store_ticket_from_charge(charge)
            except Exception as ticket_err:
                log_sync("Ticket", charge_id, "warning", f"Falha ao gerar ticket: {str(ticket_err)}")
                # Não retornar False pois o charge foi sincronizado com sucesso

        return True
    except Exception as exc:
        error_msg = f"Erro ao sincronizar charge: {str(exc)}"
        log_sync("Charge", charge_id, "error", error_msg)
        print(f"❌ {error_msg}")
        return False


def sync_customer_to_airtable(customer_id: str = None, name: str = None, email: str = None, phone: str = None, address: dict = None) -> bool:
    """
    Synchronize customer data to Airtable Customers table.
    
    Args:
        customer_id (str): ID do cliente Stripe
        name (str): Nome do cliente
        email (str): Email do cliente
        phone (str): Telefone do cliente
        address (dict): Endereço
        
    Returns:
        bool: True se sucesso, False se erro
    """
    if not (customer_id or email):
        print("⚠️  customer_id ou email é obrigatório")
        return False

    try:
        fields = {
            "customer_id": customer_id or email,
            "name": name,
            "email": email,
            "phone": phone,
        }
        upsert_record("Customers", fields, merge_on="customer_id")
        log_sync("Customer", customer_id or email, "success", f"Cliente {name or email} sincronizado")
        return True
    except Exception as exc:
        error_msg = f"Erro ao sincronizar cliente: {str(exc)}"
        log_sync("Customer", customer_id or email, "error", error_msg)
        print(f"❌ {error_msg}")
        return False


def sync_checkout_session_to_airtable(session: dict) -> bool:
    """
    Synchronize Stripe checkout session to Airtable Checkout_Sessions table.
    """
    try:
        session_id = session.get("id")
        fields = {
            "session_id": session_id,
            "created_at": _ts_to_iso(session.get("created")),
            "status": session.get("status"),
            "mode": session.get("mode"),
            "amount_total": (session.get("amount_total") or 0) / 100,
            "currency": (session.get("currency") or "").upper(),
            "customer_id": session.get("customer"),
            "customer_email": (session.get("customer_details") or {}).get("email"),
            "payment_intent_id": session.get("payment_intent"),
            "client_reference_id": session.get("client_reference_id"),
            "livemode": session.get("livemode")
        }
        upsert_record("Checkout_Sessions", fields, merge_on="session_id")
        log_sync("CheckoutSession", session_id, "success")
        return True
    except Exception as exc:
        log_sync("CheckoutSession", session.get("id"), "error", str(exc))
        return False


def sync_payout_to_airtable(payout: dict) -> bool:
    """
    Synchronize Stripe payout to Airtable Payouts table.
    """
    try:
        payout_id = payout.get("id")
        fields = {
            "payout_id": payout_id,
            "created_at": _ts_to_iso(payout.get("created")),
            "arrival_date": _ts_to_iso(payout.get("arrival_date")),
            "status": payout.get("status"),
            "amount": (payout.get("amount") or 0) / 100,
            "currency": (payout.get("currency") or "").upper(),
        }
        upsert_record("Payouts", fields, merge_on="payout_id")
        log_sync("Payout", payout_id, "success")
        return True
    except Exception as exc:
        log_sync("Payout", payout.get("id"), "error", str(exc))
        return False


def _generate_and_store_ticket_from_charge(charge: dict) -> bool:
    """
    Internal: Generate ticket PDF from charge and store in Airtable with native attachment.
    """
    try:
        charge_id = charge.get("id")
        ticket_id = str(uuid.uuid4())
        qrcode_id = str(uuid.uuid4())

        customer_name = (charge.get("billing_details") or {}).get("name") or "Guest"
        customer_email = (charge.get("billing_details") or {}).get("email") or "N/A"
        amount = (charge.get("amount") or 0) / 100
        currency = (charge.get("currency") or "EUR").upper()
        description = charge.get("description") or "Event Ticket"

        # Generate PDF
        pdf_bytes, pdf_base64 = generate_ticket_pdf(
            ticket_id=ticket_id,
            customer_name=customer_name,
            customer_email=customer_email,
            ticket_type=description,
            quantity=1,
            price=amount,
            currency=currency,
            items=[{"description": description, "quantity": 1, "amount": amount}]
        )

        # Create QR code record
        qrcode_data = generate_qrcode_data(ticket_id, customer_email)
        qr_fields = {
            "qrcode_id": qrcode_id,
            "ticket_id": ticket_id,
            "data": qrcode_data,
            "created_at": datetime.now(tz=timezone.utc).isoformat(),
            "status": "active"
        }
        upsert_record("QRCodes", qr_fields, merge_on="qrcode_id")

        # Create ticket record first (without attachment)
        # IMPORTANTE: Usar charge_id como chave para evitar duplicatas
        pdf_size_bytes = len(pdf_bytes) if pdf_bytes else 0
        ticket_fields = {
            "ticket_id": ticket_id,
            "qrcode_id": qrcode_id,
            "charge_id": charge_id,
            "customer_email": customer_email,
            "customer_name": customer_name,
            "ticket_type": description,
            "quantity": 1,
            "price": amount,
            "currency": currency,
            "pdf_size_bytes": pdf_size_bytes,
            "created_at": datetime.now(tz=timezone.utc).isoformat(),
            "status": "generated"
        }
        ticket_record = upsert_record("Tickets", ticket_fields, merge_on="charge_id")
        
        # Extract record ID for attachment upload - IMPROVED
        record_id = None
        if ticket_record and isinstance(ticket_record, dict):
            # Try multiple response formats
            if "records" in ticket_record and len(ticket_record.get("records", [])) > 0:
                record_id = ticket_record["records"][0].get("id")
                print(f"[DEBUG] Found record ID from records array: {record_id}")
            elif "id" in ticket_record:
                record_id = ticket_record.get("id")
                print(f"[DEBUG] Found record ID directly: {record_id}")
        
        print(f"[INFO] Ticket {ticket_id} created | Record ID: {record_id} | PDF size: {pdf_size_bytes} bytes")
        
        if record_id and pdf_bytes:
            try:
                # Upload PDF directly to Airtable attachment field
                from airtable_client import upload_attachment_to_record
                print(f"[INFO] Uploading PDF to {record_id}...")
                attachment_response = upload_attachment_to_record(
                    table="Tickets",
                    record_id=record_id,
                    pdf_bytes=pdf_bytes,
                    filename=f"ticket_{ticket_id}.pdf"
                )
                num_attachments = len(attachment_response) if attachment_response else 0
                print(f"[SUCCESS] PDF uploaded successfully - {num_attachments} attachment(s)")
                log_pdf_generation(ticket_id, "success", file_size=pdf_size_bytes)
            except Exception as attach_err:
                import traceback
                error_msg = f"Attachment upload failed: {str(attach_err)}"
                print(f"[ERROR] {error_msg}")
                print(f"[TRACEBACK] {traceback.format_exc()}")
                # Log warning but don't fail - ticket record exists
                log_pdf_generation(ticket_id, "warning", error=error_msg)
        else:
            error_msg = f"Cannot upload attachment - record_id: {record_id}, pdf_bytes: {len(pdf_bytes) if pdf_bytes else 0}"
            print(f"[WARNING] {error_msg}")
            log_pdf_generation(ticket_id, "warning", error=error_msg)

        return True

    except Exception as exc:
        import traceback
        error_msg = str(exc)
        print(f"[ERROR] Exception in _generate_and_store_ticket_from_charge: {error_msg}")
        print(f"[TRACEBACK] {traceback.format_exc()}")
        log_pdf_generation(charge.get("id"), "error", error=error_msg)
        return False


def generate_ticket_for_charge(charge_id: str, auto_retrieve=True) -> bool:
    """
    Generate and store a ticket for an existing charge.
    """
    try:
        if auto_retrieve and stripe_key:
            charge = stripe.Charge.retrieve(charge_id)
        else:
            charge = {"id": charge_id}

        return _generate_and_store_ticket_from_charge(charge)
    except Exception as exc:
        log_pdf_generation(charge_id, "error", error=str(exc))
        return False
