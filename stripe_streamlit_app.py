# =========================================================
# CONFIGURAÇÃO E DEPENDÊNCIAS
# =========================================================
import os
import stripe
import streamlit as st
import pandas as pd
import plotly.express as px
import re
import requests
import cv2
from streamlit_webrtc import webrtc_streamer, VideoTransformerBase
from dotenv import load_dotenv
from datetime import datetime, date, timezone, timedelta
from airtable_client import upsert_record
from stripe_airtable_payloads import (
    build_charge_fields,
    build_customer_fields_from_charge,
    build_customer_fields_from_session,
    build_payment_intent_fields,
    build_checkout_session_fields
)
from create_airtable_schema import ensure_schema
from stripe_airtable_sync import sync_charge_to_airtable, set_stripe_key
from qrcode_manager import validate_qrcode, mark_ticket_as_validated, get_ticket_data, get_ticket_by_charge_id
from stripe_field_mapping_utils import (
    load_mapping,
    save_mapping,
    load_inventory,
    ensure_object_block,
    DEFAULT_FIELD_TEMPLATE,
    MAPPING_PATH,
    INVENTORY_PATH,
)
from stripe_paid_cache import get_cache_path, load_paid_cache

# ---------------------------------------------------------
# CONFIG
# ---------------------------------------------------------
load_dotenv()

STRIPE_API_KEY = os.getenv("STRIPE_API_KEY")

# Configurar Stripe key para módulo de sync
set_stripe_key(STRIPE_API_KEY)
if not STRIPE_API_KEY:
    st.error("STRIPE_API_KEY não encontrada no .env")
    st.stop()

stripe.api_key = STRIPE_API_KEY

st.set_page_config(
    page_title="Stripe Dashboard",
    layout="wide"
)

# =========================================================
# SERVICES (Stripe API)
# =========================================================
def _to_unix_date(dt_value, end_of_day=False):
    if dt_value is None:
        return None
    if isinstance(dt_value, datetime):
        dt = dt_value
    else:
        dt = datetime.combine(
            dt_value,
            datetime.max.time() if end_of_day else datetime.min.time()
        )
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def _fetch_all(list_callable, params, max_records=None):
    data = []
    for item in list_callable(**params).auto_paging_iter():
        data.append(item)
        if max_records and len(data) >= max_records:
            break
    return data


@st.cache_data(ttl=180)
def get_charges(created_from=None, created_to=None, max_records=1000):
    params = {
        "limit": 100,
        "expand": ["data.customer"],
    }
    created = {}
    if created_from is not None:
        created["gte"] = created_from
    if created_to is not None:
        created["lte"] = created_to
    if created:
        params["created"] = created
    return _fetch_all(stripe.Charge.list, params, max_records=max_records)

@st.cache_data(ttl=180)
def get_invoices(created_from=None, created_to=None, max_records=1000):
    params = {
        "limit": 100,
        "expand": ["data.customer", "data.lines.data.price"],
    }
    created = {}
    if created_from is not None:
        created["gte"] = created_from
    if created_to is not None:
        created["lte"] = created_to
    if created:
        params["created"] = created
    return _fetch_all(stripe.Invoice.list, params, max_records=max_records)

@st.cache_data(ttl=300)
def get_customers(max_records=1000):
    params = {"limit": 100}
    return _fetch_all(stripe.Customer.list, params, max_records=max_records)

@st.cache_data(ttl=300)
def get_payouts(created_from=None, created_to=None, max_records=500):
    params = {"limit": 100}
    created = {}
    if created_from is not None:
        created["gte"] = created_from
    if created_to is not None:
        created["lte"] = created_to
    if created:
        params["created"] = created
    return _fetch_all(stripe.Payout.list, params, max_records=max_records)

@st.cache_data(ttl=300)
def get_products(max_records=1000):
    params = {"limit": 100}
    return _fetch_all(stripe.Product.list, params, max_records=max_records)

@st.cache_data(ttl=300)
def get_prices(max_records=1000):
    params = {"limit": 100, "expand": ["data.product"]}
    return _fetch_all(stripe.Price.list, params, max_records=max_records)


@st.cache_data(ttl=180)
def get_checkout_sessions(created_from=None, created_to=None, max_records=1000):
    params = {
        "limit": 100,
        "expand": ["data.customer", "data.customer_details"],
    }
    created = {}
    if created_from is not None:
        created["gte"] = created_from
    if created_to is not None:
        created["lte"] = created_to
    if created:
        params["created"] = created
    return _fetch_all(stripe.checkout.Session.list, params, max_records=max_records)


@st.cache_data(ttl=600)
def scrape_receipt_items(receipt_url):
    """Extrai itens do HTML do recibo da Stripe via receipt_url."""
    if not receipt_url:
        return []
    try:
        resp = requests.get(receipt_url, timeout=10)
        if resp.status_code != 200:
            return []
        html = resp.text
        items = []
        for block in re.findall(r"Table-description[^<]*</td>.*?Table-amount[^<]*</td>", html, flags=re.S):
            desc_match = re.search(r"Table-description[^>]*>([^<]+)", block)
            amt_match = re.search(r"Table-amount[^>]*>([^<]+)", block)
            desc_raw = desc_match.group(1).strip() if desc_match else ""
            amount_raw = amt_match.group(1).strip() if amt_match else ""

            qty = None
            desc_clean = desc_raw
            qty_match = re.search(r"[×x]\s*(\d+)", desc_raw)
            if qty_match:
                qty = int(qty_match.group(1))
                desc_clean = re.sub(r"\s*[×x]\s*\d+", "", desc_raw).strip()

            amount_value = None
            amount_clean = re.sub(r"[^\d,.-]", "", amount_raw)
            amount_clean = amount_clean.replace(",", ".")
            if amount_clean:
                try:
                    amount_value = float(amount_clean)
                except Exception:
                    amount_value = None
            if qty is None and desc_raw:
                qty = 1

            items.append({
                "description": desc_clean or desc_raw,
                "quantity": qty,
                "amount": amount_value,
                "amount_raw": amount_raw,
            })
        # remover subtotal/linhas sem produto
        return [i for i in items if i.get("description") and not str(i.get("description")).lower().startswith("subtotal")]
    except Exception:
        return []

def build_product_lookup(products):
    lookup = {}
    for prod in products:
        lookup[prod["id"]] = {
            "name": prod.get("name"),
            "description": prod.get("description"),
            "default_price": prod.get("default_price")
        }
    return lookup


def build_price_lookup(prices):
    lookup = {}
    for price in prices:
        product = price.get("product")
        product_id = product.get("id") if isinstance(product, dict) else product
        lookup[price["id"]] = {
            "product_id": product_id,
            "product_name": product.get("name") if isinstance(product, dict) else None,
            "description": price.get("nickname"),
            "unit_amount": price.get("unit_amount"),
            "currency": price.get("currency")
        }
    return lookup


def build_invoice_line_lookup(invoices):
    lookup = {}
    for inv in invoices:
        lines = []
        for item in inv.get("lines", {}).get("data", []):
            price = item.get("price", {})
            product = price.get("product")
            product_id = product.get("id") if isinstance(product, dict) else product
            lines.append({
                "product_id": product_id,
                "price_id": price.get("id"),
                "quantity": item.get("quantity", 1),
                "amount": item.get("amount", 0)/100,
                "currency": item.get("currency")
            })
        lookup[inv["id"]] = lines
    return lookup


def build_session_lookup(sessions):
    lookup = {}
    for s in sessions:
        pi = s.get("payment_intent")
        if pi and pi not in lookup:
            lookup[pi] = s
    return lookup


def _session_product_name(session):
    try:
        line_items = session.get("line_items", {}).get("data", [])
        if line_items:
            item = line_items[0]
            price = item.get("price", {})
            product = price.get("product")
            if isinstance(product, dict):
                return product.get("name") or price.get("nickname") or "Produto"
            return price.get("nickname") or "Produto"
    except Exception:
        pass
    return "Produto"


def _pick_first(*values):
    for value in values:
        if value:
            return value
    return ""


def _resolve_name_email_phone(session, charge=None):
    details = (session.get("customer_details") or {}) if session else {}
    collected = (session.get("collected_information") or {}) if session else {}
    charge_billing = (charge.get("billing_details") or {}) if charge else {}
    shipping = (charge.get("shipping") or {}) if charge else {}

    name = _pick_first(
        details.get("name"),
        details.get("individual_name"),
        collected.get("individual_name"),
        details.get("business_name"),
        charge_billing.get("name"),
        shipping.get("name"),
        charge.get("customer_name") if charge else None,
        charge.get("receipt_name") if charge else None,
    )

    email = _pick_first(
        details.get("email"),
        charge_billing.get("email"),
        charge.get("receipt_email") if charge else None,
    )

    phone = _pick_first(
        details.get("phone"),
        charge_billing.get("phone"),
    )

    return name or "Sem nome", email, phone


def build_dashboard_rows(sessions, charges):
    rows = []
    charge_by_pi = {}
    for ch in charges:
        pi = ch.get("payment_intent")
        if pi and pi not in charge_by_pi:
            charge_by_pi[pi] = ch

    for s in sessions:
        if s.get("line_items") is None:
            s = fetch_checkout_session_by_id(s.get("id")) or s
        details = s.get("customer_details") or {}
        name, email, phone = _resolve_name_email_phone(s, charge_by_pi.get(s.get("payment_intent")))
        if not name:
            name = "Sem nome"
        rows.append({
            "data": pd.to_datetime(s.get("created"), unit="s"),
            "valor": (s.get("amount_total") or 0) / 100,
            "moeda": (s.get("currency") or "").upper(),
            "status": s.get("payment_status") or s.get("status"),
            "produto": _session_product_name(s),
            "cliente": name,
            "email": email,
            "telefone": phone,
            "session_name": details.get("name"),
            "session_individual_name": details.get("individual_name"),
            "session_email": details.get("email"),
            "session_phone": details.get("phone"),
            "checkout_session": s.get("id"),
            "payment_intent": s.get("payment_intent"),
            "mensagem": None,
        })

        if s.get("custom_fields"):
            for field in s.get("custom_fields"):
                value = (field.get("text") or {}).get("value") if isinstance(field.get("text"), dict) else field.get("value")
                if value:
                    rows[-1]["mensagem"] = value
                    break

    # fallback for charges without sessions
    for ch in charges:
        pi = ch.get("payment_intent")
        if not pi or any(r.get("payment_intent") == pi for r in rows):
            continue
        billing = ch.get("billing_details", {})
        name, email, phone = _resolve_name_email_phone({}, ch)
        if not name:
            name = "Sem nome"
        rows.append({
            "data": pd.to_datetime(ch.get("created"), unit="s"),
            "valor": (ch.get("amount") or 0) / 100,
            "moeda": (ch.get("currency") or "").upper(),
            "status": ch.get("status"),
            "produto": ch.get("description") or "Produto",
            "cliente": name,
            "email": email,
            "telefone": phone,
            "session_name": None,
            "session_individual_name": None,
            "session_email": None,
            "session_phone": None,
            "checkout_session": None,
            "payment_intent": pi,
            "mensagem": None,
        })

    return pd.DataFrame(rows)


def resolve_product_details(product_id, price_id, product_lookup, price_lookup):
    details = {
        "product_id": product_id,
        "price_id": price_id,
        "name": None,
        "description": None,
        "unit_amount": None,
        "currency": None
    }

    if product_id and product_id in product_lookup:
        prod = product_lookup[product_id]
        details["name"] = prod.get("name")
        details["description"] = prod.get("description")
        details["price_id"] = details["price_id"] or prod.get("default_price")

    if price_id and price_id in price_lookup:
        price = price_lookup[price_id]
        details["unit_amount"] = price.get("unit_amount")
        details["currency"] = price.get("currency")
        if not details["product_id"]:
            details["product_id"] = price.get("product_id")
        if not details["name"]:
            details["name"] = price.get("product_name")
        if not details["description"]:
            details["description"] = price.get("description")

    return details


CHECKOUT_SESSION_CACHE = {}
CHECKOUT_SESSION_ID_CACHE = {}
CHECKOUT_SESSION_BY_PI_CACHE = None
CHECKOUT_SESSION_RECENT = None
CHECKOUT_SESSION_RECENT_LIMIT = 200


def fetch_checkout_session(payment_intent_id):
    if not payment_intent_id:
        return None
    if payment_intent_id in CHECKOUT_SESSION_CACHE:
        return CHECKOUT_SESSION_CACHE[payment_intent_id]
    try:
        sessions = stripe.checkout.Session.list(
            payment_intent=payment_intent_id,
            limit=1,
            expand=[
                "data.line_items.data.price.product",
                "data.customer",
                "data.customer_details"
            ]
        )
        session = sessions["data"][0] if sessions and sessions["data"] else None
    except Exception:
        session = None

    # Fallback: cache recent sessions and match by payment_intent
    if session is None:
        session = _lookup_recent_session_by_payment_intent(payment_intent_id)

    if session is not None:
        CHECKOUT_SESSION_CACHE[payment_intent_id] = session
    return session




def _load_recent_sessions():
    global CHECKOUT_SESSION_BY_PI_CACHE, CHECKOUT_SESSION_RECENT
    if CHECKOUT_SESSION_BY_PI_CACHE is None or CHECKOUT_SESSION_RECENT is None:
        try:
            sessions = stripe.checkout.Session.list(
                limit=CHECKOUT_SESSION_RECENT_LIMIT,
                expand=[
                    "data.line_items.data.price.product",
                    "data.customer",
                    "data.customer_details"
                ]
            )
            recent = sessions.get("data") or []
            CHECKOUT_SESSION_RECENT = recent
            CHECKOUT_SESSION_BY_PI_CACHE = {
                s.get("payment_intent"): s
                for s in recent
                if s.get("payment_intent")
            }
        except Exception:
            CHECKOUT_SESSION_RECENT = []
            CHECKOUT_SESSION_BY_PI_CACHE = {}
    return CHECKOUT_SESSION_RECENT


def _lookup_recent_session_by_payment_intent(payment_intent_id):
    _load_recent_sessions()
    return CHECKOUT_SESSION_BY_PI_CACHE.get(payment_intent_id)


def _match_session_by_charge(charge):
    sessions = _load_recent_sessions()
    if not sessions:
        return None

    ch_amount = charge.get("amount")
    ch_created = charge.get("created")
    ch_email = (
        charge.get("billing_details", {}).get("email")
        or (charge.get("customer_details") or {}).get("email")
        or charge.get("receipt_email")
    )
    if ch_amount is None or ch_created is None or not ch_email:
        return None

    # match by email + amount + time window (24h)
    candidates = []
    for s in sessions:
        details = s.get("customer_details") or {}
        if (details.get("email") or "").lower() != ch_email.lower():
            continue
        if s.get("amount_total") != ch_amount:
            continue
        if s.get("payment_status") not in ("paid", None) and s.get("status") not in ("complete", None):
            continue
        if abs((s.get("created") or 0) - ch_created) > 86400:
            continue
        candidates.append(s)

    if not candidates:
        return None
    candidates.sort(key=lambda s: s.get("created", 0), reverse=True)
    return candidates[0]


def fetch_checkout_session_by_id(session_id):
    if not session_id:
        return None
    if session_id in CHECKOUT_SESSION_ID_CACHE:
        return CHECKOUT_SESSION_ID_CACHE[session_id]
    try:
        session = stripe.checkout.Session.retrieve(
            session_id,
            expand=["customer", "customer_details", "line_items.data.price.product"]
        )
    except Exception:
        session = None
    if session is not None:
        CHECKOUT_SESSION_ID_CACHE[session_id] = session
    return session

# =========================================================
# DOMAIN — VENDAS
# =========================================================
def build_sales_dataframe(
    charges,
    invoices,
    product_lookup,
    price_lookup,
    invoice_line_lookup,
    sessions_by_pi=None,
    enable_receipt_scrape=False,
    allow_session_fetch=True
):
    rows = []

    invoice_cache = {inv["id"]: inv for inv in invoices}

    for ch in charges:
        invoice_id = ch.get("invoice")
        product_id = None
        price_id = None
        quantidade = None
        session_id = ch.get("checkout_session") or (ch.get("metadata") or {}).get("checkout_session")
        session = None
        if sessions_by_pi and ch.get("payment_intent"):
            session = sessions_by_pi.get(ch.get("payment_intent"))
        if allow_session_fetch:
            if not session:
                session = fetch_checkout_session(ch.get("payment_intent")) if ch.get("payment_intent") else None
            if not session and session_id:
                session = fetch_checkout_session_by_id(session_id)
            if not session:
                session = _match_session_by_charge(ch)
        if invoice_id and invoice_id in invoice_line_lookup:
            line = invoice_line_lookup[invoice_id][0] if invoice_line_lookup[invoice_id] else None
            if line:
                product_id = line.get("product_id")
                price_id = line.get("price_id")
                quantidade = line.get("quantity")
        if not product_id:
            if session and session.get("line_items"):
                li = session["line_items"]["data"][0]
                price = li.get("price", {})
                price_id = price.get("id")
                prod = price.get("product")
                product_id = prod.get("id") if isinstance(prod, dict) else prod
                quantidade = li.get("quantity")

        product_meta = resolve_product_details(product_id, price_id, product_lookup, price_lookup)
        customer_details = ch.get("customer_details") or {}
        session_customer = session.get("customer_details") if session else {}
        session_customer_obj = session.get("customer") if session and isinstance(session.get("customer"), dict) else {}
        email = (
            session_customer.get("email")
            or session_customer_obj.get("email")
            or customer_details.get("email")
            or ch.get("billing_details", {}).get("email")
            or ch.get("receipt_email")
        )
        phone = (
            session_customer.get("phone")
            or session_customer_obj.get("phone")
            or customer_details.get("phone")
            or ch.get("billing_details", {}).get("phone")
        )
        customer_id = ch.get("customer")
        flat_charge = pd.json_normalize([ch], sep="__").iloc[0].to_dict()
        charge_fields = {f"charge__{k}": v for k, v in flat_charge.items()}
        receipt_url = ch.get("receipt_url") or flat_charge.get("receipt_url")
        receipt_items = scrape_receipt_items(receipt_url) if (enable_receipt_scrape and receipt_url) else []
        # custom message from checkout_session custom_fields
        msg_custom = None
        if session and session.get("custom_fields"):
            for field in session.get("custom_fields"):
                key = field.get("key")
                value = (field.get("text") or {}).get("value") if isinstance(field.get("text"), dict) else field.get("value")
                if key and value:
                    msg_custom = value
                    break
        produto_nome = (
            product_meta.get("name")
            or flat_charge.get("calculated_statement_descriptor")
            or flat_charge.get("statement_descriptor")
            or (receipt_items[0]["description"] if receipt_items else None)
            or product_id
            or "Produto não identificado"
        )
        if receipt_items and (quantidade is None or quantidade == 0):
            quantidade = receipt_items[0].get("quantity") or quantidade
        if quantidade is None:
            quantidade = int(round((ch["amount"] / 100) / 15))
        rows.append({
            "id": ch["id"],
            "tipo": "Charge",
            "valor": ch["amount"] / 100,
            "moeda": ch["currency"].upper(),
            "status": ch["status"],
            "data": pd.to_datetime(ch["created"], unit="s"),
            "cliente": email or customer_id,
            "cliente_email": email,
            "cliente_phone": phone,
            "cliente_id": customer_id,
            "session_id": session_id or (session.get("id") if session else None),
            "nome_cliente": (
                (session_customer.get("name") or session_customer.get("individual_name") if isinstance(session_customer, dict) else None)
                or (session_customer_obj.get("name") if isinstance(session_customer_obj, dict) else None)
                or (customer_details.get("name") or customer_details.get("individual_name") if isinstance(customer_details, dict) else None)
                or ch.get("billing_details", {}).get("name")
                or (ch.get("shipping") or {}).get("name")
                or ch.get("customer_name")
                or ch.get("receipt_name")
                or customer_id
                or ""
            ),
            "mensagem_custom": msg_custom,
            "descricao": ch.get("description"),
            "quantidade": quantidade,
            "produto_nome": produto_nome,
            "produto_descricao": product_meta.get("description"),
            "produto_preco": product_meta.get("unit_amount"),
            "produto_moeda": product_meta.get("currency"),
            "produto_id": product_meta.get("product_id") or product_id,
            "preco_id": product_meta.get("price_id") or price_id,
            "endereco": ch.get("billing_details", {}).get("address"),
            **charge_fields
        })

    for inv in invoices:
        email_cliente = None
        customer_id = None
        nome_cliente = ""
        if isinstance(inv.get("customer"), dict):
            nome_cliente = inv["customer"].get("name", "")
            email_cliente = inv["customer"].get("email")
            customer_id = inv["customer"].get("id")
        else:
            customer_id = inv.get("customer")
        email_cliente = email_cliente or inv.get("customer_email")
        # Pega o primeiro item da invoice para produto/preço (pode ser adaptado para múltiplos)
        produto_id = None
        preco_id = None
        lines = inv.get("lines", {}).get("data", [])
        lines = invoice_line_lookup.get(inv["id"], [])
        if lines:
            first_line = lines[0]
            produto_id = first_line.get("product_id")
            preco_id = first_line.get("price_id")
        product_meta = resolve_product_details(
            produto_id.get("id") if isinstance(produto_id, dict) else produto_id,
            preco_id,
            product_lookup,
            price_lookup
        )
        quantidade_total = sum(line.get("quantity", 0) for line in lines) if lines else None
        produto_nome = ", ".join([
            resolve_product_details(
                line.get("product_id"),
                line.get("price_id"),
                product_lookup,
                price_lookup
            ).get("name") or line.get("product_id") or "Produto"
            for line in lines
        ]) if lines else product_meta.get("name")
        rows.append({
            "id": inv["id"],
            "tipo": "Invoice",
            "valor": inv["amount_paid"] / 100,
            "moeda": inv["currency"].upper(),
            "status": inv["status"],
            "data": pd.to_datetime(inv["created"], unit="s"),
            "cliente": email_cliente or customer_id,
            "cliente_email": email_cliente,
            "cliente_id": customer_id,
            "nome_cliente": nome_cliente,
            "descricao": "Invoice",
            "produto_id": product_meta.get("product_id"),
            "preco_id": product_meta.get("price_id"),
            "quantidade": quantidade_total,
            "produto_nome": produto_nome or product_meta.get("name") or "Produto não identificado",
            "produto_descricao": product_meta.get("description"),
            "produto_preco": product_meta.get("unit_amount"),
            "produto_moeda": product_meta.get("currency"),
            "endereco": inv.get("customer_address")
        })

    return pd.DataFrame(rows)

def sales_metrics(df):
    total = df["valor"].sum()
    count = len(df)
    ticket = total / count if count else 0
    return total, count, ticket

# =========================================================
# DOMAIN — CLIENTES
# =========================================================
def build_customers_dataframe(customers, df_sales):
    from collections import OrderedDict

    agg = OrderedDict()

    def upsert_entry(customer_id, nome, email, valor=0.0, endereco=None):
        key = (str(customer_id) if customer_id else "", email or "")
        if key not in agg:
            agg[key] = {
                "id": customer_id,
                "nome": nome,
                "email": email,
                "total_comprado": 0.0,
                "num_compras": 0,
                "endereco": endereco
            }
        entry = agg[key]
        if not entry["nome"] and nome:
            entry["nome"] = nome
        if not entry["email"] and email:
            entry["email"] = email
        if not entry["endereco"] and endereco:
            entry["endereco"] = endereco
        entry["total_comprado"] += valor or 0.0
        if valor is not None:
            entry["num_compras"] += 1 if valor > 0 else 0

    # Primeiro, garantimos que os clientes vindos da API apareçam
    for c in customers:
        upsert_entry(
            c.get("id"),
            c.get("name"),
            c.get("email"),
            valor=0.0,
            endereco=c.get("address")
        )

    # Agora adicionamos/atualizamos com base nas vendas
    if not df_sales.empty:
        for _, venda in df_sales.iterrows():
            upsert_entry(
                venda.get("cliente_id"),
                venda.get("nome_cliente"),
                venda.get("cliente_email"),
                valor=venda.get("valor", 0.0),
                endereco=venda.get("endereco")
            )

    return pd.DataFrame(list(agg.values())) if agg else pd.DataFrame()

# =========================================================
# DOMAIN — RECEBIMENTOS
# =========================================================
def build_payouts_dataframe(payouts):
    rows = []

    for p in payouts:
        rows.append({
            "id": p["id"],
            "valor": p["amount"] / 100,
            "moeda": p["currency"].upper(),
            "status": p["status"],
            "data": pd.to_datetime(p["created"], unit="s"),
            "chegada_prevista": pd.to_datetime(p["arrival_date"], unit="s")
        })

    return pd.DataFrame(rows)

# =========================================================
# UI — SIDEBAR
# =========================================================
st.sidebar.title("Stripe Dashboard")
if st.sidebar.button("🔁 Atualizar agora"):
    st.cache_data.clear()
    CHECKOUT_SESSION_CACHE.clear()
    CHECKOUT_SESSION_ID_CACHE.clear()
    CHECKOUT_SESSION_BY_PI_CACHE = None
    CHECKOUT_SESSION_RECENT = None
    for key in [
        "stripe_payload",
        "stripe_payload_key",
        "df_sales_cache",
        "df_sales_cache_key",
        "df_dashboard_cache",
        "df_dashboard_cache_key",
        "df_clientes_cache",
        "df_clientes_cache_key",
        "df_payouts_cache",
        "df_payouts_cache_key",
    ]:
        st.session_state.pop(key, None)
    st.rerun()

menu = st.sidebar.radio(
    "Navegação",
    [
        "Dashboard",
        "Vendas",
        "Clientes",
        "Recebimentos",
        "Detalhes",
        "Bilhetes",
        "Picking",
        "Campos",
        "Admin"
    ]
)

st.sidebar.subheader("Modo e filtros")
fast_mode = st.sidebar.checkbox("Modo rápido (15 dias / 300 reg.)", value=True)
today = date.today()

cache_path = get_cache_path()
cache_available = os.path.exists(cache_path)
use_webhook_cache = st.sidebar.checkbox("Usar cache do webhook (pagos)", value=cache_available)
if use_webhook_cache and not cache_available:
    st.sidebar.caption("Cache do webhook não encontrado ainda.")

if fast_mode:
    start_date = today - timedelta(days=15)
    end_date = today
    created_from = _to_unix_date(start_date, end_of_day=False)
    created_to = _to_unix_date(end_date, end_of_day=True)
    max_records = 300
    st.sidebar.caption("Modo rápido limita a 300 registros e 15 dias para carregar mais rápido.")
else:
    date_range = st.sidebar.date_input(
        "Período",
        value=(today - timedelta(days=30), today)
    )
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date = date_range
        end_date = date_range

    created_from = _to_unix_date(start_date, end_of_day=False)
    created_to = _to_unix_date(end_date, end_of_day=True)

    load_all = st.sidebar.checkbox("Carregar tudo (pode demorar)", value=False)
    max_records = None if load_all else st.sidebar.slider(
        "Máx. registros por lista",
        min_value=100,
        max_value=5000,
        value=800,
        step=100
    )


@st.cache_data(ttl=10)
def _load_paid_cache_cached(path, mtime):
    return load_paid_cache(path)

def _get_session_cache(cache_key, cache_slot, builder):
    if st.session_state.get(f"{cache_slot}_key") == cache_key and cache_slot in st.session_state:
        return st.session_state[cache_slot]
    value = builder()
    st.session_state[cache_slot] = value
    st.session_state[f"{cache_slot}_key"] = cache_key
    return value

# =========================================================
# LOAD DATA (c/ cache por sessão)
# =========================================================
charges = []
invoices = []
customers_raw = []
payouts_raw = []
sessions_raw = []
products_raw = []
prices_raw = []

product_lookup = {}
price_lookup = {}
invoice_line_lookup = {}
session_lookup = {}

df_sales = pd.DataFrame()
df_dashboard = pd.DataFrame()
df_clientes = pd.DataFrame()
df_payouts = pd.DataFrame()
df_sales_paid = pd.DataFrame()
total_vendas = 0
num_vendas = 0
ticket_medio = 0

if menu != "Campos" and menu != "Picking":
    use_paid_cache = use_webhook_cache and cache_available and menu in {"Dashboard", "Vendas", "Clientes"}

    if use_paid_cache:
        with st.spinner("A carregar cache do webhook..."):
            cache_mtime = os.path.getmtime(cache_path) if cache_available else 0
            paid_cache = _load_paid_cache_cached(cache_path, cache_mtime)
            charges = list((paid_cache.get("charges") or {}).values())
            sessions_raw = list((paid_cache.get("sessions") or {}).values())
            session_lookup = build_session_lookup(sessions_raw)

            if menu == "Dashboard":
                df_dashboard = build_dashboard_rows(sessions_raw, charges)
            if menu in {"Vendas", "Clientes"}:
                df_sales = build_sales_dataframe(
                    charges,
                    [],
                    {},
                    {},
                    {},
                    session_lookup,
                    enable_receipt_scrape=False,
                    allow_session_fetch=False
                )
            if menu == "Clientes":
                df_clientes = build_customers_dataframe([], df_sales)

            if not df_sales.empty:
                df_sales_paid = df_sales[df_sales["status"] == "succeeded"]
                total_vendas, num_vendas, ticket_medio = sales_metrics(df_sales_paid)
    else:
        needs_charges = menu in {"Dashboard", "Vendas", "Clientes", "Detalhes", "Bilhetes", "Admin"}
        needs_invoices = menu in {"Vendas", "Clientes", "Detalhes", "Admin"}
        needs_customers = menu in {"Clientes"}
        needs_payouts = menu in {"Recebimentos"}
        needs_sessions = menu in {"Dashboard", "Vendas", "Clientes"}
        needs_products = menu in {"Vendas", "Clientes", "Detalhes"}
        needs_prices = menu in {"Vendas", "Clientes", "Detalhes"}

        payload_key = (
            created_from,
            created_to,
            max_records,
            needs_charges,
            needs_invoices,
            needs_customers,
            needs_payouts,
            needs_sessions,
            needs_products,
            needs_prices,
        )

        def _load_payload():
            data = {}
            if needs_charges:
                data["charges"] = get_charges(created_from=created_from, created_to=created_to, max_records=max_records)
            if needs_invoices:
                data["invoices"] = get_invoices(created_from=created_from, created_to=created_to, max_records=max_records)
            if needs_customers:
                data["customers"] = get_customers(max_records=max_records)
            if needs_payouts:
                data["payouts"] = get_payouts(created_from=created_from, created_to=created_to, max_records=max_records)
            if needs_sessions:
                data["sessions"] = get_checkout_sessions(created_from=created_from, created_to=created_to, max_records=max_records)
            if needs_products:
                data["products"] = get_products(max_records=max_records)
            if needs_prices:
                data["prices"] = get_prices(max_records=max_records)
            return data

        with st.spinner("A carregar dados da Stripe..."):
            payload = _get_session_cache(payload_key, "stripe_payload", _load_payload)
            charges = payload.get("charges", [])
            invoices = payload.get("invoices", [])
            customers_raw = payload.get("customers", [])
            payouts_raw = payload.get("payouts", [])
            sessions_raw = payload.get("sessions", [])
            products_raw = payload.get("products", [])
            prices_raw = payload.get("prices", [])

            if needs_products:
                product_lookup = build_product_lookup(products_raw)
            if needs_prices:
                price_lookup = build_price_lookup(prices_raw)
            if needs_invoices:
                invoice_line_lookup = build_invoice_line_lookup(invoices)
            if needs_sessions:
                session_lookup = build_session_lookup(sessions_raw)

            if menu == "Dashboard":
                df_dashboard = _get_session_cache(
                    (payload_key, "dashboard"),
                    "df_dashboard_cache",
                    lambda: build_dashboard_rows(sessions_raw, charges)
                )
            if menu in {"Vendas", "Clientes"}:
                df_sales = _get_session_cache(
                    (payload_key, "sales", False),
                    "df_sales_cache",
                    lambda: build_sales_dataframe(
                        charges,
                        invoices,
                        product_lookup,
                        price_lookup,
                        invoice_line_lookup,
                        session_lookup,
                        enable_receipt_scrape=False
                    )
                )
            if menu == "Clientes":
                df_clientes = _get_session_cache(
                    (payload_key, "clientes"),
                    "df_clientes_cache",
                    lambda: build_customers_dataframe(customers_raw, df_sales)
                )
            if menu == "Recebimentos":
                df_payouts = _get_session_cache(
                    (payload_key, "payouts"),
                    "df_payouts_cache",
                    lambda: build_payouts_dataframe(payouts_raw)
                )

            if not df_sales.empty:
                df_sales_paid = df_sales[df_sales["status"] == "succeeded"]
                total_vendas, num_vendas, ticket_medio = sales_metrics(df_sales_paid)

# =========================================================
# UI — DASHBOARD
# =========================================================
if menu == "Dashboard":
    st.title("📊 Visão Geral")

    if df_dashboard.empty:
        st.info("Nenhuma venda encontrada no período selecionado.")
    else:
        df_dash_paid = df_dashboard[df_dashboard["status"].isin(["paid", "succeeded", "complete", "paid_out", "succeeded"])].copy()
        total_dash = df_dash_paid["valor"].sum()
        count_dash = len(df_dash_paid)
        ticket_dash = total_dash / count_dash if count_dash else 0

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Vendido", f"€ {total_dash:,.2f}")
        c2.metric("Nº de Vendas", count_dash)
        c3.metric("Ticket Médio", f"€ {ticket_dash:,.2f}")

        st.divider()
        st.caption("Dados diretos da Stripe (checkout.session). Atualize no menu lateral para recarregar.")

        st.subheader("Últimas vendas (Stripe)")
        if df_dash_paid.empty:
            st.info("Sem vendas pagas no período selecionado.")
        recentes = df_dash_paid.sort_values("data", ascending=False).head(12)
        tabela = recentes[[
            "data",
            "valor",
            "moeda",
            "status",
            "produto",
            "session_name",
            "session_individual_name",
            "session_email",
            "session_phone",
            "payment_intent"
        ]].copy()
        tabela.rename(columns={
            "data": "Data",
            "valor": "Valor",
            "moeda": "Moeda",
            "status": "Status",
            "produto": "Produto",
            "session_name": "Nome (checkout)",
            "session_individual_name": "Nome individual",
            "session_email": "Email (checkout)",
            "session_phone": "Telefone (checkout)",
            "payment_intent": "Payment Intent"
        }, inplace=True)
        tabela["Valor"] = tabela["Valor"].apply(
            lambda v: f"€ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if pd.notnull(v) else ""
        )
        st.dataframe(tabela, width="stretch", hide_index=True)

        st.subheader("Mensagens personalizadas")
        if "mensagem" in df_dash_paid.columns:
            msgs = df_dash_paid.dropna(subset=["mensagem"]).copy()
            msgs = msgs[msgs["mensagem"].astype(str).str.strip() != ""]
        else:
            msgs = pd.DataFrame()
        if not msgs.empty:
            cards = msgs[["cliente", "email", "telefone", "mensagem", "data"]].fillna("")
            cards = cards.sort_values("data", ascending=False).head(12)
            for _, row in cards.iterrows():
                header = row["cliente"] or row["email"] or "Cliente"
                detail = []
                if row["email"]:
                    detail.append(row["email"])
                if row["telefone"]:
                    detail.append(row["telefone"])
                meta = " • ".join(detail)
                st.info(f"**{header}**{f' ({meta})' if meta else ''}\n{row['mensagem']}")
        else:
            st.info("Nenhuma mensagem personalizada encontrada nas vendas deste período.")

    st.divider()

# =========================================================
# UI — CAMPOS (Mapeamento de dados)
# =========================================================
elif menu == "Campos":
    st.title("🧭 Mapeamento de Campos")
    st.caption("Controle total dos campos recebidos da Stripe e onde cada um será usado.")

    mapping = load_mapping()
    inventory = load_inventory(default={}) or {}
    mapping_objects = mapping.get("objects", {})

    if not mapping_objects:
        st.warning("Nenhum objeto configurado ainda. Execute stripe_field_inspector.py para gerar o inventário inicial.")
        st.code("python stripe_field_inspector.py --limit 50")
        st.caption(f"Arquivo alvo: {MAPPING_PATH}")
        st.caption(f"Inventário: {INVENTORY_PATH}")
    else:
        options = sorted(mapping_objects.keys())
        label_lookup = {key: mapping_objects[key].get("label") or key.replace("_", " ").title() for key in options}
        selected = st.selectbox(
            "Objeto Stripe",
            options,
            format_func=lambda key: label_lookup.get(key, key.title())
        )

        obj_block = ensure_object_block(mapping, selected, label_lookup.get(selected))
        field_map = obj_block.get("fields", {})
        inv_fields = ((inventory.get("objects") or {}).get(selected) or {}).get("fields", {})

        if not field_map:
            st.info("Ainda não há campos mapeados. Execute stripe_field_inspector.py para gerar a lista automaticamente.")
            st.code("python stripe_field_inspector.py --limit 50")
            st.caption(f"Inventário esperado em {INVENTORY_PATH}")
        else:
            rows = []
            for field_path in sorted(field_map.keys()):
                entry = field_map[field_path]
                inv_info = inv_fields.get(field_path, {})
                rows.append({
                    "field": field_path,
                    "description": entry.get("description", ""),
                    "use_dashboard": entry.get("use_dashboard", False),
                    "use_airtable": entry.get("use_airtable", False),
                    "use_webhook": entry.get("use_webhook", False),
                    "use_sync": entry.get("use_sync", False),
                    "notes": entry.get("notes", ""),
                    "last_example": entry.get("last_example") or (inv_info.get("examples", [None])[0] if inv_info else None),
                    "last_type": entry.get("last_type") or (inv_info.get("types", [None])[0] if inv_info else None),
                })

            show_only_marked = st.checkbox("Mostrar apenas campos já utilizados", value=False)
            if show_only_marked:
                rows = [row for row in rows if any([row.get("use_dashboard"), row.get("use_airtable"), row.get("use_webhook"), row.get("use_sync")])]

            if not rows:
                st.info("Sem campos para mostrar com o filtro atual.")
            else:
                editable_df = pd.DataFrame(rows)
                edited = st.data_editor(
                    editable_df,
                    hide_index=True,
                    num_rows="fixed",
                    use_container_width=True,
                    column_config={
                        "field": st.column_config.TextColumn("Campo", disabled=True),
                        "description": st.column_config.TextColumn("Descrição"),
                        "use_dashboard": st.column_config.CheckboxColumn("Dashboard"),
                        "use_airtable": st.column_config.CheckboxColumn("Airtable"),
                        "use_webhook": st.column_config.CheckboxColumn("Webhook"),
                        "use_sync": st.column_config.CheckboxColumn("Sync/ETL"),
                        "notes": st.column_config.TextColumn("Notas"),
                        "last_example": st.column_config.TextColumn("Último exemplo", disabled=True),
                        "last_type": st.column_config.TextColumn("Tipo", disabled=True)
                    },
                    key=f"mapping_editor_{selected}"
                )

                if st.button("💾 Guardar alterações", key=f"save_mapping_{selected}"):
                    records = edited.to_dict("records")
                    updated = 0
                    for record in records:
                        field_entry = field_map.setdefault(record["field"], dict(DEFAULT_FIELD_TEMPLATE))
                        field_entry["description"] = record.get("description", "")
                        field_entry["use_dashboard"] = bool(record.get("use_dashboard"))
                        field_entry["use_airtable"] = bool(record.get("use_airtable"))
                        field_entry["use_webhook"] = bool(record.get("use_webhook"))
                        field_entry["use_sync"] = bool(record.get("use_sync"))
                        field_entry["notes"] = record.get("notes", "")
                        updated += 1
                    save_mapping(mapping)
                    st.success(f"Mapeamento atualizado ({updated} campos salvos).")
                    st.caption(f"Arquivo: {MAPPING_PATH}")
                    st.rerun()

# =========================================================
# UI — ADMIN (Airtable / Sincronização)
# =========================================================
elif menu == "Admin":
    st.title("⚙️ Admin / Airtable")
    st.caption("Centralize aqui as ações pesadas: schema, sincronização e geração de PDFs.")

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Aplicar schema no Airtable"):
            try:
                ensure_schema()
                st.success("Schema aplicado com sucesso.")
            except Exception as exc:
                st.error("Falha ao aplicar schema via API. Use o arquivo airtable_schema.json manualmente.")
                st.write(str(exc))

    with col_b:
        max_sync = st.number_input(
            "Máx. registros para sincronizar",
            min_value=10,
            max_value=2000,
            value=200,
            step=10,
            key="max_sync_airtable"
        )

    st.subheader("Sincronizar Charges")
    if st.button("Enviar Charges para Airtable"):
        synced = 0
        tickets_generated = 0
        errors = 0
        for ch in charges[:max_sync]:
            try:
                fields = build_charge_fields(ch)
                upsert_record("Charges", fields, merge_on="charge_id")
                customer_fields = build_customer_fields_from_charge(ch)
                if customer_fields.get("customer_id") or customer_fields.get("email"):
                    upsert_record("Customers", customer_fields, merge_on="customer_id")
                synced += 1

                if ch.get("status") == "succeeded":
                    existing_ticket = get_ticket_by_charge_id(ch.get("id"))
                    if not existing_ticket.get("success"):
                        from stripe_airtable_sync import _generate_and_store_ticket_from_charge
                        if _generate_and_store_ticket_from_charge(ch):
                            tickets_generated += 1
            except Exception:
                errors += 1

        st.success(f"✅ Charges sincronizadas: {synced} | Bilhetes gerados: {tickets_generated} | Erros: {errors}")

    st.subheader("Sincronizar Charges COM Geração de Bilhetes")
    if st.button("Enviar Charges + Gerar Bilhetes PDF"):
        synced = 0
        tickets_generated = 0
        errors = 0
        progress_bar = st.progress(0)
        status_placeholder = st.empty()

        for idx, ch in enumerate(charges[:max_sync]):
            try:
                fields = build_charge_fields(ch)
                upsert_record("Charges", fields, merge_on="charge_id")
                customer_fields = build_customer_fields_from_charge(ch)
                if customer_fields.get("customer_id") or customer_fields.get("email"):
                    upsert_record("Customers", customer_fields, merge_on="customer_id")
                synced += 1

                from stripe_airtable_sync import _generate_and_store_ticket_from_charge
                if _generate_and_store_ticket_from_charge(ch):
                    tickets_generated += 1

                progress_bar.progress((idx + 1) / min(max_sync, len(charges)))
                status_placeholder.info(f"Processados: {idx + 1} | Sincronizados: {synced} | Bilhetes: {tickets_generated}")
            except Exception as e:
                errors += 1
                status_placeholder.warning(f"Erro em {ch.get('id')}: {str(e)}")

        progress_bar.progress(1.0)
        st.success(f"✅ Charges sincronizadas: {synced} | Bilhetes gerados: {tickets_generated} | Erros: {errors}")

    st.subheader("Sincronizar Payment Intents")
    if st.button("Enviar Payment Intents para Airtable"):
        synced = 0
        errors = 0
        for inv in invoices[:max_sync]:
            pi = inv.get("payment_intent")
            if not pi:
                continue
            try:
                pi_obj = stripe.PaymentIntent.retrieve(pi, expand=["charges.data"])
                charge_id = None
                receipt_url = None
                charges_data = pi_obj.get("charges", {}).get("data", []) if isinstance(pi_obj, dict) else pi_obj.charges.data
                if charges_data:
                    charge_id = charges_data[0].get("id")
                    receipt_url = charges_data[0].get("receipt_url")
                fields = build_payment_intent_fields(pi_obj, charge_id=charge_id, receipt_url=receipt_url)
                upsert_record("Payment_Intents", fields, merge_on="payment_intent_id")
                synced += 1
            except Exception:
                errors += 1
        st.success(f"Payment Intents sincronizados: {synced}. Erros: {errors}.")

    st.subheader("Sincronizar Checkout Sessions")
    if st.button("Enviar Checkout Sessions para Airtable"):
        synced = 0
        errors = 0
        for inv in invoices[:max_sync]:
            try:
                if inv.get("payment_intent"):
                    sessions = stripe.checkout.Session.list(payment_intent=inv.get("payment_intent"), limit=1)
                    if not sessions.data:
                        continue
                    session = sessions.data[0]
                else:
                    continue

                receipt_url = None
                if session.get("payment_intent"):
                    pi_obj = stripe.PaymentIntent.retrieve(session.get("payment_intent"), expand=["charges.data"])
                    charges_data = pi_obj.get("charges", {}).get("data", []) if isinstance(pi_obj, dict) else pi_obj.charges.data
                    if charges_data:
                        receipt_url = charges_data[0].get("receipt_url")

                fields = build_checkout_session_fields(session, receipt_url=receipt_url)
                upsert_record("Checkout_Sessions", fields, merge_on="session_id")
                customer_fields = build_customer_fields_from_session(session)
                if customer_fields.get("customer_id") or customer_fields.get("email"):
                    upsert_record("Customers", customer_fields, merge_on="customer_id")
                synced += 1
            except Exception:
                errors += 1
        st.success(f"Checkout Sessions sincronizadas: {synced}. Erros: {errors}.")

# =========================================================
# UI — VENDAS
# =========================================================
elif menu == "Vendas":
    st.title("💳 Vendas")

    mostrar_charge = st.checkbox("Mostrar colunas brutas (charge__*)", value=False)
    status_filter = st.selectbox("Status", ["succeeded", "pending", "failed", "all"], index=0)

    df = df_sales.copy()
    if status_filter != "all":
        df = df[df["status"] == status_filter]
    df = df.sort_values("data", ascending=False)
    col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
    col_kpi1.metric("Valor filtrado", f"€ {df['valor'].sum():,.2f}")
    col_kpi2.metric("Vendas", len(df))
    ticket_filtrado = df["valor"].mean() if not df.empty else 0
    col_kpi3.metric("Ticket médio", f"€ {ticket_filtrado:,.2f}")

    if df.empty:
        st.warning("Nenhuma venda encontrada para os filtros selecionados.")
    else:
        fig = px.bar(
            df,
            x="data",
            y="valor",
            color="produto_nome",
            hover_data={
                "nome_cliente": True,
                "produto_nome": True,
                "status": True,
                "valor": ":.2f"
            },
            labels={"data": "Data", "valor": "Valor", "produto_nome": "Produto"},
            title="Distribuição das vendas filtradas"
        )
        fig.update_traces(marker_line_width=0)
        fig.update_layout(legend_title_text="Produto", hovermode="x unified")
        st.plotly_chart(fig, width=1200)

        coluna_moeda = df["produto_moeda"].fillna(df["moeda"])
        cols_base = [
            "id", "tipo", "status", "data", "valor", "moeda",
            "nome_cliente", "cliente_email", "cliente_phone",
            "produto_nome", "quantidade", "produto_preco", "produto_moeda", "descricao"
        ]
        cols_extra = [c for c in df.columns if c.startswith("charge__")]
        cols_tabela = cols_base + cols_extra if mostrar_charge else cols_base

        tabela = df[cols_tabela].copy()
        tabela["produto_preco"] = tabela["produto_preco"].apply(lambda x: x / 100 if pd.notnull(x) else None)
        tabela.rename(columns={
            "id": "ID",
            "tipo": "Tipo",
            "status": "Status",
            "data": "Data",
            "valor": "Valor (€)",
            "moeda": "Moeda",
            "nome_cliente": "Cliente",
            "cliente_email": "Email",
            "charge__billing_details__phone": "Telefone",
            "produto_nome": "Produto",
            "quantidade": "Qtd",
            "produto_preco": "Preço Produto",
            "produto_moeda": "Moeda Produto",
            "descricao": "Descrição"
        }, inplace=True)
        if "Valor (€)" in tabela.columns:
            tabela["Valor (€)"] = tabela["Valor (€)"].apply(
                lambda v: f"€ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                if pd.notnull(v)
                else ""
            )
        st.dataframe(tabela, width="stretch")

        st.subheader("Análise de Produtos")
        df_prod = df.copy()
        df_prod["produto_nome"] = df_prod["produto_nome"].fillna("Produto não identificado")
        df_prod["quantidade"] = df_prod["quantidade"].fillna(0)
        resumo = (
            df_prod.groupby("produto_nome", as_index=False)
            .agg(
                vendas=("valor", "sum"),
                num_vendas=("id", "count"),
                quantidade=("quantidade", "sum")
            )
            .sort_values("vendas", ascending=False)
        )
        if resumo.empty:
            st.info("Nenhum dado de produto disponível para análise.")
        else:
            fig_prod = px.bar(
                resumo,
                x="produto_nome",
                y="vendas",
                title="Vendas por Produto",
                labels={"produto_nome": "Produto", "vendas": "Vendas (€)"}
            )
            fig_prod.update_traces(marker_line_width=0)
            st.plotly_chart(fig_prod, width=1200)
            st.dataframe(resumo, width="stretch")

        st.subheader("Produtos extraídos do recibo (scraping receipt_url)")
        carregar_recibos = st.checkbox("Carregar itens de recibo (lento)", value=False)
        if carregar_recibos:
            receipt_rows = []
            for _, linha in df.iterrows():
                receipt_url = linha.get("charge__receipt_url") or linha.get("receipt_url")
                if not receipt_url:
                    continue
                for item in scrape_receipt_items(receipt_url):
                    receipt_rows.append({
                        "Charge ID": linha.get("charge__id") or linha.get("id"),
                        "Produto (recibo)": item.get("description"),
                        "Quantidade (recibo)": item.get("quantity"),
                        "Valor (recibo)": item.get("amount"),
                        "Receipt URL": receipt_url,
                    })
            df_receipt = pd.DataFrame(receipt_rows)
            if df_receipt.empty:
                st.info("Nenhum dado de recibo captado ou receipt_url ausente.")
            else:
                if "Valor (recibo)" in df_receipt.columns:
                    df_receipt["Valor (recibo)"] = df_receipt["Valor (recibo)"].apply(
                        lambda v: f"€ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                        if pd.notnull(v)
                        else ""
                    )
                st.dataframe(df_receipt, width="stretch")
        else:
            st.info("Ative a opção acima para carregar os itens do recibo (mais lento).")

    # Tabela de produtos vendidos por invoice
    st.subheader("Produtos e Quantidades Vendidos (Invoices)")
    produtos = []
    for inv_id, lines in invoice_line_lookup.items():
        for line in lines:
            details = resolve_product_details(
                line.get("product_id"),
                line.get("price_id"),
                product_lookup,
                price_lookup
            )
            produtos.append({
                "invoice_id": inv_id,
                "produto": details.get("name") or line.get("product_id") or "Produto",
                "produto_id": details.get("product_id") or line.get("product_id"),
                "preco_produto_id": details.get("price_id") or line.get("price_id"),
                "descricao_produto": details.get("description") or "",
                "quantidade": line.get("quantity"),
                "valor_unitario": details.get("unit_amount") / 100 if details.get("unit_amount") is not None else line.get("amount"),
                "moeda": details.get("currency") or line.get("currency")
            })
    df_produtos = pd.DataFrame(produtos)
    if not df_produtos.empty:
        st.dataframe(df_produtos, width="stretch")
    else:
        st.info("Nenhum produto vendido encontrado nas invoices.")

# =========================================================
# UI — CLIENTES
# =========================================================
elif menu == "Clientes":
    st.title("👥 Clientes")
    paid_statuses = {"succeeded", "paid", "complete", "paid_out"}
    paid_df = df_sales[df_sales["status"].isin(paid_statuses)].copy() if not df_sales.empty else pd.DataFrame()

    total_customers = 0
    if not df_clientes.empty and "email" in df_clientes.columns:
        total_customers = (
            df_clientes["email"].fillna("").replace("", pd.NA).dropna().nunique()
        )
    if total_customers == 0 and not df_sales.empty:
        total_customers = (
            df_sales.get("cliente_email", pd.Series(dtype=str))
            .fillna("")
            .replace("", pd.NA)
            .dropna()
            .nunique()
        )

    paying_customers = 0
    if not paid_df.empty:
        paying_customers = (
            paid_df.get("cliente_email", pd.Series(dtype=str))
            .fillna("")
            .replace("", pd.NA)
            .dropna()
            .nunique()
        )

    abandoned_rows = []
    if sessions_raw:
        for s in sessions_raw:
            payment_status = s.get("payment_status")
            status = s.get("status")
            if payment_status == "paid" or status == "complete":
                continue
            details = s.get("customer_details") or {}
            customer_obj = s.get("customer") if isinstance(s.get("customer"), dict) else {}
            email = details.get("email") or customer_obj.get("email")
            name = details.get("name") or customer_obj.get("name")
            phone = details.get("phone") or customer_obj.get("phone")
            amount_total = s.get("amount_total")
            abandoned_rows.append({
                "Data": pd.to_datetime(s.get("created"), unit="s") if s.get("created") else None,
                "Nome": name,
                "Email": email,
                "Telefone": phone,
                "Status": status or payment_status,
                "Total": (amount_total / 100) if amount_total is not None else None,
                "Session ID": s.get("id")
            })

    abandoned_customers = 0
    if abandoned_rows:
        df_abandoned = pd.DataFrame(abandoned_rows)
        abandoned_customers = (
            df_abandoned.get("Email", pd.Series(dtype=str))
            .fillna("")
            .replace("", pd.NA)
            .dropna()
            .nunique()
        )
    conversion_rate = (paying_customers / total_customers * 100) if total_customers else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total de clientes", total_customers)
    c2.metric("Clientes pagantes", paying_customers)
    c3.metric("Taxa de conversão", f"{conversion_rate:.1f}%")
    c4.metric("Abandonos", abandoned_customers)

    st.subheader("Ranking de Clientes Pagantes")
    if not paid_df.empty:
        paid_customers = (
            paid_df.groupby(["cliente_email", "nome_cliente"], dropna=False)
            .agg(total_pago=("valor", "sum"), num_compras=("id", "count"))
            .reset_index()
            .sort_values("total_pago", ascending=False)
        )
        paid_customers.rename(columns={
            "cliente_email": "Email",
            "nome_cliente": "Nome",
            "total_pago": "Total Pago (€)",
            "num_compras": "Nº Compras"
        }, inplace=True)
        paid_customers["Total Pago (€)"] = paid_customers["Total Pago (€)"].apply(
            lambda v: f"€ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            if pd.notnull(v)
            else ""
        )
        st.dataframe(paid_customers.fillna(""), width="stretch")
    else:
        st.info("Nenhuma compra paga encontrada para o período selecionado.")

    st.subheader("Checkouts não concluídos")
    if abandoned_rows:
        df_abandoned = pd.DataFrame(abandoned_rows).sort_values("Data", ascending=False)
        if "Total" in df_abandoned.columns:
            df_abandoned["Total"] = df_abandoned["Total"].apply(
                lambda v: f"€ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                if pd.notnull(v)
                else ""
            )
        st.dataframe(df_abandoned.fillna(""), width="stretch")
    else:
        st.info("Nenhum checkout não concluído encontrado (ou cache só contém pagos).")

    st.subheader("Detalhe do Cliente")
    selector_rows = []
    if not df_clientes.empty:
        for _, row in df_clientes.iterrows():
            selector_rows.append({
                "id": row.get("id"),
                "email": row.get("email"),
                "nome": row.get("nome")
            })
    elif not df_sales.empty:
        base = df_sales[["cliente_email", "nome_cliente"]].dropna(how="all").drop_duplicates()
        for _, row in base.iterrows():
            selector_rows.append({
                "id": None,
                "email": row.get("cliente_email"),
                "nome": row.get("nome_cliente")
            })

    if selector_rows:
        df_selector = pd.DataFrame(selector_rows).fillna("")

        def _format_row(idx):
            row = df_selector.loc[idx]
            label_email = row.get("email") or row.get("id") or "Sem identificador"
            label_nome = row.get("nome") or "Sem nome"
            return f"{label_nome} - {label_email}"

        selected_idx = st.selectbox(
            "Selecionar cliente",
            df_selector.index,
            format_func=_format_row
        )

        cliente_sel = df_selector.loc[selected_idx]
        email_sel = cliente_sel.get("email") or None
        id_sel = cliente_sel.get("id") or None

        if df_sales.empty:
            detalhe = df_sales
        else:
            email_series = df_sales.get("cliente_email")
            if email_series is None:
                email_series = df_sales["cliente"].copy()
            email_series = email_series.fillna("")

            id_series = df_sales.get("cliente_id")
            if id_series is None:
                id_series = pd.Series([None] * len(df_sales), index=df_sales.index)
            id_series = id_series.fillna("").astype(str)

            mask_email = pd.Series(False, index=df_sales.index)
            if email_sel:
                mask_email = email_series.str.lower() == str(email_sel).lower()

            mask_id = pd.Series(False, index=df_sales.index)
            if id_sel:
                mask_id = id_series == str(id_sel)

            detalhe = df_sales[mask_email | mask_id]

        if detalhe.empty:
            st.info("Nenhuma compra encontrada para este cliente.")
        else:
            detalhe_display = detalhe.copy()
            if "charge__id" not in detalhe_display.columns:
                detalhe_display["charge__id"] = detalhe_display.get("id")
            if "metodo_pagamento" not in detalhe_display.columns:
                detalhe_display["metodo_pagamento"] = detalhe_display.get("charge__payment_method_details__type")
            cols_cliente = [
                "data",
                "produto_nome",
                "quantidade",
                "valor",
                "moeda",
                "status",
                "metodo_pagamento",
                "charge__id",
                "charge__receipt_url",
                "charge__payment_intent",
                "cliente_email",
                "nome_cliente"
            ]
            cols_presentes = [c for c in cols_cliente if c in detalhe_display.columns]
            detalhe_display = detalhe_display[cols_presentes].rename(columns={
                "data": "Data",
                "produto_nome": "Produto",
                "quantidade": "Quantidade",
                "valor": "Valor",
                "moeda": "Moeda",
                "status": "Status",
                "metodo_pagamento": "Metodo Pagamento",
                "charge__id": "Charge ID",
                "charge__receipt_url": "Receipt URL",
                "charge__payment_intent": "Payment Intent",
                "cliente_email": "Email Cliente",
                "nome_cliente": "Nome Cliente"
            })
            if "Valor" in detalhe_display.columns:
                detalhe_display["Valor"] = detalhe_display["Valor"].apply(
                    lambda v: f"€ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    if pd.notnull(v)
                    else ""
                )
            st.dataframe(detalhe_display, width="stretch")
    else:
        st.info("Nenhum cliente disponível para seleção.")

# =========================================================
# UI — RECEBIMENTOS
# =========================================================

elif menu == "Recebimentos":
    st.title("🏦 Recebimentos (Payouts)")
    if not df_payouts.empty and "data" in df_payouts.columns:
        st.dataframe(
            df_payouts.sort_values("data", ascending=False),
            width="stretch"
        )
    else:
        st.info("Nenhum recebimento encontrado ou dados incompletos.")

# =========================================================
# UI — DETALHES / AUDITORIA
# =========================================================
elif menu == "Detalhes":
    st.title("🔍 Auditoria")

    st.subheader("Invoices")
    for inv in invoices:
        with st.expander(inv["id"]):
            st.write(f"Status: {inv['status']}")
            st.write(f"Valor pago: € {inv['amount_paid']/100:.2f}")
            st.write(pd.to_datetime(inv["created"], unit="s"))
            st.write("Produtos vendidos:")
            for line in invoice_line_lookup.get(inv["id"], []):
                details = resolve_product_details(
                    line.get("product_id"),
                    line.get("price_id"),
                    product_lookup,
                    price_lookup
                )
                st.write({
                    "Produto": details.get("name") or line.get("product_id") or "Produto",
                    "Quantidade": line.get("quantity", 1),
                    "Valor unitário": f"{(details.get('unit_amount') or 0)/100:.2f} {(details.get('currency') or line.get('currency') or '').upper()}"
                })

    st.subheader("Charges")
    for ch in charges:
        with st.expander(ch["id"]):
            st.write(f"Status: {ch['status']}")
            st.write(f"Valor: € {ch['amount']/100:.2f}")
            st.write(pd.to_datetime(ch["created"], unit="s"))
            st.markdown("**Dados brutos do Charge:**")
            st.json(ch)
            # Tentar buscar dados do Checkout Session associado (se houver)
            checkout_id = ch.get("checkout_session") or ch.get("metadata", {}).get("checkout_session")
            if not checkout_id:
                # Tentar buscar pelo campo payment_intent
                pi = ch.get("payment_intent")
                if pi:
                    # Buscar sessions associadas ao payment_intent
                    try:
                        sessions = stripe.checkout.Session.list(payment_intent=pi, limit=1)
                        if sessions and sessions.data:
                            checkout_id = sessions.data[0]["id"]
                    except Exception:
                        pass
            if checkout_id:
                st.markdown(f"**Checkout Session:** {checkout_id}")
                try:
                    session = stripe.checkout.Session.retrieve(checkout_id)
                    st.json(session)
                except Exception as e:
                    st.warning(f"Não foi possível obter dados do Checkout Session: {e}")

# =========================================================
# UI — BILHETES
# =========================================================
elif menu == "Bilhetes":
    st.title("🎫 Geração de Bilhetes")
    st.caption("Gere bilhetes em PDF com QR code para validação na entrada.")

    st.subheader("Diagnóstico rápido (PDF/QR)")
    if charges:
        max_check = st.slider(
            "Quantas últimas charges verificar",
            min_value=1,
            max_value=min(50, len(charges)),
            value=min(20, len(charges)),
            step=1
        )
        if st.button("Verificar bilhetes gerados"):
            resultados = []
            for ch in charges[:max_check]:
                ticket_info = get_ticket_by_charge_id(ch.get("id"))
                status = ticket_info.get("status") if ticket_info.get("success") else "não encontrado"
                pdf_ok = bool(ticket_info.get("pdf_url")) if ticket_info.get("success") else False
                resultados.append({
                    "charge_id": ch.get("id"),
                    "valor": ch.get("amount", 0) / 100,
                    "status_ticket": status,
                    "pdf": "ok" if pdf_ok else "ausente",
                    "ticket_id": ticket_info.get("ticket_id") or "-"
                })
            df_diag = pd.DataFrame(resultados)
            if not df_diag.empty:
                df_diag["valor"] = df_diag["valor"].apply(lambda v: f"€ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                st.dataframe(df_diag, width="stretch", hide_index=True)
    else:
        st.info("Nenhuma charge carregada para diagnóstico.")

    st.subheader("Gerar Bilhete a partir de Charge")
    
    col_b1, col_b2 = st.columns(2)
    with col_b1:
        if charges:
            charge_options = {ch["id"]: f"{ch['id'][:12]}... - € {ch['amount']/100:.2f}" for ch in charges}
            selected_charge_id = st.selectbox("Selecionar charge", options=list(charge_options.keys()), format_func=lambda x: charge_options[x])
        else:
            st.info("Nenhum charge disponível.")
            selected_charge_id = None

    with col_b2:
        auto_gen = st.checkbox("Gerar automaticamente para novos charges", value=False)

    if selected_charge_id and st.button("Gerar Bilhete"):
        with st.spinner("A gerar bilhete..."):
            charge = next((ch for ch in charges if ch["id"] == selected_charge_id), None)
            if charge:
                success = sync_charge_to_airtable(charge, auto_generate_ticket=True)
                if success:
                    st.success("Bilhete gerado com sucesso!")
                    st.info(f"PDF guardado em Airtable com QR code para validação.")
                else:
                    st.error("Erro ao gerar bilhete.")

    st.subheader("Sincronização em Lote")
    max_batch = st.number_input("Máx. bilhetes a gerar", min_value=1, max_value=len(charges) if charges else 1, value=min(10, len(charges) if charges else 1))

    if st.button("Gerar Bilhetes em Lote"):
        with st.spinner(f"A gerar {max_batch} bilhetes..."):
            generated = 0
            for charge in charges[:max_batch]:
                try:
                    sync_charge_to_airtable(charge, auto_generate_ticket=True)
                    generated += 1
                except Exception as e:
                    st.warning(f"Erro ao gerar bilhete para {charge['id']}: {str(e)}")
            st.success(f"Bilhetes gerados: {generated}/{max_batch}")

# =========================================================
# UI — PICKING (Validação Entrada)
# =========================================================
elif menu == "Picking":
    st.title("📱 Picking - Validação de Bilhetes")
    st.caption("Valide bilhetes lendo QR codes com a câmera do telefone. Não há opção manual.")

    if "qr_last" not in st.session_state:
        st.session_state["qr_last"] = ""
    if "qr_last_ts" not in st.session_state:
        st.session_state["qr_last_ts"] = None
    if "qr_processed" not in st.session_state:
        st.session_state["qr_processed"] = ""
    if "validation_history" not in st.session_state:
        st.session_state["validation_history"] = []
    if "last_validation" not in st.session_state:
        st.session_state["last_validation"] = None

    class QRScanner(VideoTransformerBase):
        def __init__(self):
            self.detector = cv2.QRCodeDetector()

        def transform(self, frame):
            img = frame.to_ndarray(format="bgr24")
            data, _, _ = self.detector.detectAndDecode(img)
            if data:
                try:
                    if data != st.session_state.get("qr_last"):
                        st.session_state["qr_last"] = data
                        st.session_state["qr_last_ts"] = datetime.now(tz=timezone.utc).isoformat()
                except Exception:
                    pass
            return frame

    validator_name = st.text_input("Seu nome", placeholder="Porteiro/Segurança", key="validator")

    webrtc_streamer(
        key="qr-scanner",
        video_transformer_factory=QRScanner,
        media_stream_constraints={"video": {"facingMode": "environment"}, "audio": False},
        async_processing=True,
    )

    qrcode_input = st.session_state.get("qr_last")
    if qrcode_input and qrcode_input != st.session_state.get("qr_processed"):
        result = validate_qrcode(qrcode_input, validated_by=validator_name or "system")
        st.session_state["qr_processed"] = qrcode_input
        st.session_state["last_validation"] = result

        status_label = "válido" if result.get("success") else "inválido"
        if result.get("already_validated"):
            status_label = "duplicado"

        st.session_state["validation_history"].insert(0, {
            "hora": datetime.now(tz=timezone.utc).strftime("%H:%M:%S"),
            "ticket_id": result.get("ticket_id") or "N/A",
            "status": status_label,
            "validador": validator_name or "system",
            "detalhe": result.get("error") or "ok",
        })

    result = st.session_state.get("last_validation")
    if result:
        if result.get("success"):
            st.success("✅ Bilhete válido!")
            col_t1, col_t2, col_t3 = st.columns(3)
            with col_t1:
                st.metric("Ticket ID", result["ticket_id"][:12])
            with col_t2:
                st.metric("Validado por", validator_name or "system")
            with col_t3:
                st.metric("Hora", result.get("validated_at", "").split("T")[1][:5] if result.get("validated_at") else "N/A")

            if st.button("Confirmar Validação"):
                mark_ticket_as_validated(result["ticket_id"], validator_name or "system")
                st.success("Entrada registada!")
                st.balloons()
        elif result.get("already_validated"):
            st.warning("⚠️ Bilhete já validado (duplicado)")
        else:
            st.error(f"❌ Erro: {result.get('error', 'Erro desconhecido')}")

    st.divider()
    st.subheader("Histórico de validações (tempo real)")
    if st.session_state["validation_history"]:
        st.dataframe(st.session_state["validation_history"][:50], width="stretch")
    else:
        st.info("Nenhuma validação registada ainda.")
