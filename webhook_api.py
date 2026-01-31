import os
import logging

import stripe
from fastapi import FastAPI, Request, HTTPException
from dotenv import load_dotenv

from airtable_client import upsert_record
from stripe_airtable_payloads import (
    build_event_fields,
    build_customer_fields_from_charge,
    build_customer_fields_from_session,
    build_charge_fields,
    build_payment_intent_fields,
    build_checkout_session_fields
)

load_dotenv()

STRIPE_API_KEY = os.getenv("STRIPE_API_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

if STRIPE_API_KEY:
    stripe.api_key = STRIPE_API_KEY

app = FastAPI(title="Stripe Webhook API")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("stripe_webhook")


def store_event(event):
    fields = build_event_fields(event)
    upsert_record("Stripe_Events", fields, merge_on="event_id")


def upsert_customer_from_charge(charge):
    fields = build_customer_fields_from_charge(charge)
    if not fields.get("customer_id") and not fields.get("email"):
        return
    upsert_record("Customers", fields, merge_on="customer_id")


def upsert_customer_from_session(session):
    fields = build_customer_fields_from_session(session)
    if not fields.get("customer_id") and not fields.get("email"):
        return
    upsert_record("Customers", fields, merge_on="customer_id")


def handle_charge_succeeded(charge):
    fields = build_charge_fields(charge)
    upsert_record("Charges", fields, merge_on="charge_id")
    upsert_customer_from_charge(charge)


def handle_payment_intent_succeeded(pi):
    charge_id = None
    receipt_url = None
    charges = pi.get("charges", {}).get("data", [])
    if charges:
        charge_id = charges[0].get("id")
        receipt_url = charges[0].get("receipt_url")

    fields = build_payment_intent_fields(pi, charge_id=charge_id, receipt_url=receipt_url)
    upsert_record("Payment_Intents", fields, merge_on="payment_intent_id")


def _resolve_receipt_url_from_payment_intent(payment_intent_id):
    if not payment_intent_id:
        return None
    try:
        pi = stripe.PaymentIntent.retrieve(payment_intent_id, expand=["charges.data"])
        charges = pi.get("charges", {}).get("data", []) if isinstance(pi, dict) else pi.charges.data
        if charges:
            return charges[0].get("receipt_url")
    except Exception:
        return None
    return None


def handle_checkout_session_completed(session):
    receipt_url = _resolve_receipt_url_from_payment_intent(session.get("payment_intent"))
    fields = build_checkout_session_fields(session, receipt_url=receipt_url)
    upsert_record("Checkout_Sessions", fields, merge_on="session_id")
    upsert_customer_from_session(session)


def handle_event(event):
    store_event(event)
    event_type = event.get("type")
    data_obj = event.get("data", {}).get("object", {})

    if event_type == "charge.succeeded":
        handle_charge_succeeded(data_obj)
    elif event_type == "payment_intent.succeeded":
        handle_payment_intent_succeeded(data_obj)
    elif event_type == "checkout.session.completed":
        handle_checkout_session_completed(data_obj)


@app.post("/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=500, detail="STRIPE_WEBHOOK_SECRET ausente.")

    try:
        logger.info("Webhook recebido")
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=STRIPE_WEBHOOK_SECRET
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    logger.info("Evento Stripe: %s", event.get("type"))
    handle_event(event)
    return {"received": True}
