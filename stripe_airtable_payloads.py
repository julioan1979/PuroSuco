import json
from datetime import datetime, timezone


def _ts_to_iso(ts):
    if not ts:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _safe_json(obj):
    try:
        return json.dumps(obj, ensure_ascii=False)
    except Exception:
        return str(obj)


def build_event_fields(event):
    data_obj = event.get("data", {}).get("object", {})
    return {
        "event_id": event.get("id"),
        "type": event.get("type"),
        "created_at": _ts_to_iso(event.get("created")),
        "livemode": event.get("livemode"),
        "api_version": event.get("api_version"),
        "account": event.get("account"),
        "request_id": event.get("request", {}).get("id"),
        "idempotency_key": event.get("request", {}).get("idempotency_key"),
        "pending_webhooks": event.get("pending_webhooks"),
        "data_object_id": data_obj.get("id"),
        "data_object_type": data_obj.get("object"),
        "payload_json": _safe_json(event)
    }


def build_customer_fields(customer_id=None, name=None, email=None, phone=None, address=None):
    return {
        "customer_id": customer_id or email,
        "name": name,
        "email": email,
        "phone": phone,
        "address": _safe_json(address) if address else None
    }


def build_customer_fields_from_charge(charge):
    customer_id = charge.get("customer")
    billing = charge.get("billing_details", {})
    return build_customer_fields(
        customer_id=customer_id,
        name=billing.get("name"),
        email=billing.get("email"),
        phone=billing.get("phone"),
        address=billing.get("address")
    )


def build_customer_fields_from_session(session):
    customer_id = session.get("customer")
    details = session.get("customer_details", {})
    return build_customer_fields(
        customer_id=customer_id,
        name=details.get("name"),
        email=details.get("email"),
        phone=details.get("phone"),
        address=details.get("address")
    )


def build_charge_fields(charge):
    return {
        "charge_id": charge.get("id"),
        "created_at": _ts_to_iso(charge.get("created")),
        "status": charge.get("status"),
        "amount": (charge.get("amount") or 0) / 100,
        "currency": (charge.get("currency") or "").upper(),
        "customer_id": charge.get("customer"),
        "customer_email": charge.get("billing_details", {}).get("email"),
        "billing_name": charge.get("billing_details", {}).get("name"),
        "billing_phone": charge.get("billing_details", {}).get("phone"),
        "billing_address": _safe_json(charge.get("billing_details", {}).get("address"))
        if charge.get("billing_details", {}).get("address") else None,
        "description": charge.get("description"),
        "statement_descriptor": charge.get("statement_descriptor"),
        "calculated_statement_descriptor": charge.get("calculated_statement_descriptor"),
        "invoice_id": charge.get("invoice"),
        "payment_intent_id": charge.get("payment_intent"),
        "receipt_url": charge.get("receipt_url"),
        "livemode": charge.get("livemode")
    }


def build_payment_intent_fields(pi, charge_id=None, receipt_url=None):
    return {
        "payment_intent_id": pi.get("id"),
        "created_at": _ts_to_iso(pi.get("created")),
        "status": pi.get("status"),
        "amount": (pi.get("amount") or 0) / 100,
        "currency": (pi.get("currency") or "").upper(),
        "customer_id": pi.get("customer"),
        "charge_id": charge_id,
        "receipt_url": receipt_url,
        "livemode": pi.get("livemode")
    }


def build_checkout_session_fields(session, receipt_url=None):
    return {
        "session_id": session.get("id"),
        "created_at": _ts_to_iso(session.get("created")),
        "status": session.get("status"),
        "mode": session.get("mode"),
        "amount_total": (session.get("amount_total") or 0) / 100,
        "currency": (session.get("currency") or "").upper(),
        "customer_id": session.get("customer"),
        "customer_email": session.get("customer_details", {}).get("email"),
        "payment_intent_id": session.get("payment_intent"),
        "client_reference_id": session.get("client_reference_id"),
        "receipt_url": receipt_url,
        "livemode": session.get("livemode")
    }
