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
from stripe_airtable_sync import sync_charge_to_airtable
from qrcode_manager import validate_qrcode, mark_ticket_as_validated, get_ticket_data, get_ticket_by_charge_id

# ---------------------------------------------------------
# CONFIG
# ---------------------------------------------------------
load_dotenv()

STRIPE_API_KEY = os.getenv("STRIPE_API_KEY")

# Configurar Stripe key para módulo de sync
from stripe_airtable_sync import set_stripe_key
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


@st.cache_data(ttl=300)
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

@st.cache_data(ttl=300)
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

@st.cache_data(ttl=600)
def get_products(max_records=1000):
    params = {"limit": 100}
    return _fetch_all(stripe.Product.list, params, max_records=max_records)

@st.cache_data(ttl=600)
def get_prices(max_records=1000):
    params = {"limit": 100, "expand": ["data.product"]}
    return _fetch_all(stripe.Price.list, params, max_records=max_records)


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


def fetch_checkout_session(payment_intent_id):
    if not payment_intent_id:
        return None
    if payment_intent_id in CHECKOUT_SESSION_CACHE:
        return CHECKOUT_SESSION_CACHE[payment_intent_id]
    try:
        sessions = stripe.checkout.Session.list(
            payment_intent=payment_intent_id,
            limit=1,
            expand=["data.line_items.data.price.product"]
        )
        session = sessions["data"][0] if sessions and sessions["data"] else None
    except Exception:
        session = None
    CHECKOUT_SESSION_CACHE[payment_intent_id] = session
    return session

# =========================================================
# DOMAIN — VENDAS
# =========================================================
def build_sales_dataframe(charges, invoices, product_lookup, price_lookup, invoice_line_lookup):
    rows = []

    invoice_cache = {inv["id"]: inv for inv in invoices}

    for ch in charges:
        invoice_id = ch.get("invoice")
        product_id = None
        price_id = None
        quantidade = None
        if invoice_id and invoice_id in invoice_line_lookup:
            line = invoice_line_lookup[invoice_id][0] if invoice_line_lookup[invoice_id] else None
            if line:
                product_id = line.get("product_id")
                price_id = line.get("price_id")
                quantidade = line.get("quantity")
        if not product_id:
            session = fetch_checkout_session(ch.get("payment_intent"))
            if session and session.get("line_items"):
                li = session["line_items"]["data"][0]
                price = li.get("price", {})
                price_id = price.get("id")
                prod = price.get("product")
                product_id = prod.get("id") if isinstance(prod, dict) else prod
                quantidade = li.get("quantity")

        product_meta = resolve_product_details(product_id, price_id, product_lookup, price_lookup)
        email = ch.get("billing_details", {}).get("email")
        customer_id = ch.get("customer")
        flat_charge = pd.json_normalize([ch], sep="__").iloc[0].to_dict()
        charge_fields = {f"charge__{k}": v for k, v in flat_charge.items()}
        receipt_url = ch.get("receipt_url") or flat_charge.get("receipt_url")
        receipt_items = scrape_receipt_items(receipt_url) if receipt_url else []
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
            "cliente_id": customer_id,
            "nome_cliente": ch.get("billing_details", {}).get("name", ""),
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
menu = st.sidebar.radio(
    "Navegação",
    ["Dashboard", "Vendas", "Clientes", "Recebimentos", "Detalhes", "Bilhetes", "Picking"]
)

st.sidebar.subheader("Filtros")
today = date.today()
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
    value=1000,
    step=100
)

# =========================================================
# LOAD DATA (1x)
# =========================================================
with st.spinner("A carregar dados da Stripe..."):
    charges = get_charges(created_from=created_from, created_to=created_to, max_records=max_records)
    invoices = get_invoices(created_from=created_from, created_to=created_to, max_records=max_records)
    customers_raw = get_customers(max_records=max_records)
    payouts_raw = get_payouts(created_from=created_from, created_to=created_to, max_records=max_records)

    products_raw = get_products(max_records=max_records)
    prices_raw = get_prices(max_records=max_records)

    product_lookup = build_product_lookup(products_raw)
    price_lookup = build_price_lookup(prices_raw)
    invoice_line_lookup = build_invoice_line_lookup(invoices)

    df_sales = build_sales_dataframe(charges, invoices, product_lookup, price_lookup, invoice_line_lookup)
    df_clientes = build_customers_dataframe(customers_raw, df_sales)
    df_payouts = build_payouts_dataframe(payouts_raw)

    df_sales_paid = df_sales[df_sales["status"] == "succeeded"]
    total_vendas, num_vendas, ticket_medio = sales_metrics(df_sales_paid)

# =========================================================
# UI — DASHBOARD
# =========================================================
if menu == "Dashboard":
    st.title("📊 Visão Geral")

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Vendido", f"€ {total_vendas:,.2f}")
    c2.metric("Nº de Vendas", num_vendas)
    c3.metric("Ticket Médio", f"€ {ticket_medio:,.2f}")

    st.divider()

    # Sincronização Manual
    col_sync1, col_sync2 = st.columns(2)
    with col_sync1:
        if st.button("🔄 Sincronizar Agora"):
            with st.spinner("A sincronizar dados com Airtable..."):
                sync_count = 0
                ticket_count = 0
                for ch in charges[:50]:
                    try:
                        # SEMPRE sincronizar charge
                        sync_charge_to_airtable(ch, auto_generate_ticket=False)
                        sync_count += 1
                        
                        # Verificar se tem ticket E se tem pdf_url
                        if ch.get("status") == "succeeded":
                            existing_ticket = get_ticket_by_charge_id(ch.get("id"))
                            needs_pdf = False
                            
                            if not existing_ticket.get("success"):
                                needs_pdf = True
                            else:
                                # Verificar se tem pdf_url
                                from airtable_client import _headers, _table_url, get_airtable_config
                                import requests
                                api_key, base_id = get_airtable_config()
                                ticket_id = existing_ticket.get("ticket_id")
                                
                                url = _table_url(base_id, "Tickets")
                                params = {"filterByFormula": f"{{ticket_id}}='{ticket_id}'"}
                                resp = requests.get(url, headers=_headers(api_key), params=params)
                                records = resp.json().get("records", [])
                                
                                if records and not records[0].get("fields", {}).get("pdf_url"):
                                    needs_pdf = True
                            
                            if needs_pdf:
                                from stripe_airtable_sync import _generate_and_store_ticket_from_charge
                                if _generate_and_store_ticket_from_charge(ch):
                                    ticket_count += 1
                    except Exception as e:
                        print(f"[SYNC ERROR] {ch.get('id')}: {str(e)}")
                
                st.success(f"✅ Sincronizados: {sync_count} | Bilhetes gerados: {ticket_count}")
    
    with col_sync2:
        if st.button("📄 Sincronizar + Gerar PDFs"):
            with st.spinner("A sincronizar e gerar bilhetes..."):
                sync_count = 0
                ticket_count = 0
                errors = 0
                progress_bar = st.progress(0)
                
                for idx, ch in enumerate(charges[:50]):
                    try:
                        # SEMPRE sincronizar charge
                        sync_charge_to_airtable(ch, auto_generate_ticket=False)
                        sync_count += 1
                        
                        # SEMPRE gerar ticket com PDF (mesmo se já existir, atualiza)
                        from stripe_airtable_sync import _generate_and_store_ticket_from_charge
                        if _generate_and_store_ticket_from_charge(ch):
                            ticket_count += 1
                        
                        progress_bar.progress((idx + 1) / min(50, len(charges)))
                    except Exception as e:
                        errors += 1
                        print(f"[BATCH ERROR] {ch.get('id')}: {str(e)}")
                
                progress_bar.progress(1.0)
                st.success(f"✅ Sincronizados: {sync_count} | Bilhetes: {ticket_count} | Erros: {errors}")

    st.divider()

    fig = px.line(
        df_sales_paid.sort_values("data"),
        x="data",
        y="valor",
        color="tipo",
        title="Evolução das Vendas"
    )
    st.plotly_chart(fig, use_container_width=True)

    st.divider()
    with st.expander("🗃️ Airtable (sincronização manual)"):
        st.caption("Sincronize dados do Stripe para o Airtable e aplique o schema manualmente.")

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

    if "filtro_tipo" not in st.session_state:
        st.session_state["filtro_tipo"] = sorted(df_sales["tipo"].unique())
    if "filtro_status" not in st.session_state:
        st.session_state["filtro_status"] = sorted(df_sales["status"].unique())

    filtros_col = st.columns([3, 3, 1, 2])
    with filtros_col[0]:
        tipos = st.multiselect(
            "Tipo",
            sorted(df_sales["tipo"].unique()),
            key="filtro_tipo"
        )
    with filtros_col[1]:
        status = st.multiselect(
            "Status",
            sorted(df_sales["status"].unique()),
            key="filtro_status"
        )
    with filtros_col[2]:
        if st.button("Limpar filtros"):
            st.session_state["filtro_tipo"] = sorted(df_sales["tipo"].unique())
            st.session_state["filtro_status"] = sorted(df_sales["status"].unique())
            st.experimental_rerun()
    with filtros_col[3]:
        mostrar_charge = st.checkbox(
            "Mostrar dados do Charge",
            value=False
        )

    df = df_sales[
        df_sales["tipo"].isin(st.session_state["filtro_tipo"]) &
        df_sales["status"].isin(st.session_state["filtro_status"])
    ].sort_values("data")

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
        st.plotly_chart(fig, use_container_width=True)

        coluna_moeda = df["produto_moeda"].fillna(df["moeda"])
        cols_base = [
            "id", "tipo", "status", "data", "valor", "moeda",
            "nome_cliente", "cliente_email", "charge__billing_details__phone",
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
        st.dataframe(tabela, use_container_width=True)

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
            st.plotly_chart(fig_prod, use_container_width=True)
            st.dataframe(resumo, use_container_width=True)

        st.subheader("Produtos extraídos do recibo (scraping receipt_url)")
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
            st.dataframe(df_receipt, use_container_width=True)

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
        st.dataframe(df_produtos, use_container_width=True)
    else:
        st.info("Nenhum produto vendido encontrado nas invoices.")

# =========================================================
# UI — CLIENTES
# =========================================================
elif menu == "Clientes":
    st.title("👥 Clientes")


    st.subheader("Ranking de Clientes")
    if not df_clientes.empty and "total_comprado" in df_clientes.columns:
        df_display = df_clientes.copy()
        if "endereco" in df_display.columns:
            df_display["cidade"] = df_display["endereco"].apply(lambda x: x.get("city") if isinstance(x, dict) else None)
            df_display["pais"] = df_display["endereco"].apply(lambda x: x.get("country") if isinstance(x, dict) else None)
            df_display["rua"] = df_display["endereco"].apply(lambda x: x.get("line1") if isinstance(x, dict) else None)
            df_display["linha2"] = df_display["endereco"].apply(lambda x: x.get("line2") if isinstance(x, dict) else None)
            df_display["postal_code"] = df_display["endereco"].apply(lambda x: x.get("postal_code") if isinstance(x, dict) else None)
        cols_base = ["id", "nome", "email", "total_comprado", "num_compras", "rua", "linha2", "cidade", "postal_code", "pais"]
        cols_presentes = [c for c in cols_base if c in df_display.columns]
        if not cols_presentes:
            cols_presentes = ["id", "nome", "email", "total_comprado", "num_compras"]
        st.dataframe(
            df_display[cols_presentes].fillna("") if cols_presentes else df_display,
            use_container_width=True
        )
    else:
        st.info("Nenhum cliente encontrado ou dados incompletos.")

    if not df_clientes.empty:
        def _format(idx):
            row = df_clientes.loc[idx]
            label_email = row.get("email") or row.get("id") or "Sem identificador"
            label_nome = row.get("nome") or "Sem nome"
            return f"{label_nome} - {label_email}"

        selected_idx = st.selectbox(
            "Selecionar cliente",
            df_clientes.index,
            format_func=_format
        )

        cliente_sel = df_clientes.loc[selected_idx]
        email_sel = cliente_sel.get("email")
        id_sel = cliente_sel.get("id")

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
                mask_email = email_series.str.lower() == email_sel.lower()

            mask_id = pd.Series(False, index=df_sales.index)
            if id_sel:
                mask_id = id_series == str(id_sel)

            detalhe = df_sales[mask_email | mask_id]

        st.subheader("Compras do Cliente")
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
            st.dataframe(detalhe_display, use_container_width=True)

# =========================================================
# UI — RECEBIMENTOS
# =========================================================

elif menu == "Recebimentos":
    st.title("🏦 Recebimentos (Payouts)")
    if not df_payouts.empty and "data" in df_payouts.columns:
        st.dataframe(
            df_payouts.sort_values("data", ascending=False),
            use_container_width=True
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
        st.dataframe(st.session_state["validation_history"][:50], use_container_width=True)
    else:
        st.info("Nenhuma validação registada ainda.")
