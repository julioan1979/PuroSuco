#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para sincronizar dados do Streamlit para Airtable.
Execute manualmente ou como job agendado.
"""
import os
import sys
from dotenv import load_dotenv
import stripe
from datetime import datetime, timedelta

load_dotenv()

# Adicionar diretório ao path
sys.path.insert(0, os.path.dirname(__file__))

from stripe_airtable_sync import (
    set_stripe_key,
    sync_charge_to_airtable,
    sync_customer_to_airtable,
    sync_checkout_session_to_airtable,
    sync_payout_to_airtable
)
from app_logger import log_action

STRIPE_API_KEY = os.getenv("STRIPE_API_KEY")

if not STRIPE_API_KEY:
    print("ERRO: STRIPE_API_KEY não encontrada em .env")
    sys.exit(1)

set_stripe_key(STRIPE_API_KEY)
stripe.api_key = STRIPE_API_KEY


def sync_all_charges(limit=100, days_back=30):
    """Sincronizar todos os charges dos últimos N dias."""
    print(f"A sincronizar charges dos últimos {days_back} dias...")
    
    start_ts = int((datetime.now() - timedelta(days=days_back)).timestamp())
    charges = stripe.Charge.list(limit=limit, created={'gte': start_ts})
    
    synced = 0
    errors = 0
    
    for charge in charges.data:
        try:
            sync_charge_to_airtable(charge, auto_generate_ticket=False)
            synced += 1
            print(f"  ✓ Charge {charge['id'][:12]}... sincronizado")
        except Exception as e:
            errors += 1
            print(f"  ✗ Erro: {charge['id'][:12]}... - {str(e)}")
    
    print(f"Resultado: {synced} sincronizados, {errors} erros")
    log_action("sync", "sync_all_charges", f"success" if errors == 0 else "partial", 
               f"Sincronizados: {synced}, Erros: {errors}")


def sync_all_customers(limit=100):
    """Sincronizar todos os customers."""
    print("A sincronizar customers...")
    
    customers = stripe.Customer.list(limit=limit)
    synced = 0
    errors = 0
    
    for customer in customers.data:
        try:
            sync_customer_to_airtable(
                customer_id=customer.get('id'),
                name=customer.get('name'),
                email=customer.get('email'),
                phone=customer.get('phone')
            )
            synced += 1
            print(f"  ✓ Customer {customer['id'][:12]}... sincronizado")
        except Exception as e:
            errors += 1
            print(f"  ✗ Erro: {customer['id'][:12]}... - {str(e)}")
    
    print(f"Resultado: {synced} sincronizados, {errors} erros")


def sync_all_checkout_sessions(limit=100, days_back=30):
    """Sincronizar todos os checkout sessions."""
    print(f"A sincronizar checkout sessions dos últimos {days_back} dias...")
    
    start_ts = int((datetime.now() - timedelta(days=days_back)).timestamp())
    sessions = stripe.checkout.Session.list(limit=limit, created={'gte': start_ts})
    
    synced = 0
    errors = 0
    
    for session in sessions.data:
        try:
            sync_checkout_session_to_airtable(session)
            synced += 1
            print(f"  ✓ Session {session['id'][:12]}... sincronizado")
        except Exception as e:
            errors += 1
            print(f"  ✗ Erro: {session['id'][:12]}... - {str(e)}")
    
    print(f"Resultado: {synced} sincronizados, {errors} erros")


def sync_all_payouts(limit=100, days_back=365):
    """Sincronizar todos os payouts dos últimos N dias."""
    print(f"A sincronizar payouts dos últimos {days_back} dias...")
    
    start_ts = int((datetime.now() - timedelta(days=days_back)).timestamp())
    payouts = stripe.Payout.list(limit=limit, created={'gte': start_ts})
    
    synced = 0
    errors = 0
    
    for payout in payouts.data:
        try:
            sync_payout_to_airtable(payout)
            synced += 1
            print(f"  ✓ Payout {payout['id'][:12]}... sincronizado")
        except Exception as e:
            errors += 1
            print(f"  ✗ Erro: {payout['id'][:12]}... - {str(e)}")
    
    print(f"Resultado: {synced} sincronizados, {errors} erros")
    log_action("sync", "sync_all_payouts", f"success" if errors == 0 else "partial", 
               f"Sincronizados: {synced}, Erros: {errors}")


if __name__ == "__main__":
    print("=" * 60)
    print("SINCRONIZAÇÃO STRIPE → AIRTABLE")
    print("=" * 60)
    
    sync_all_charges(limit=100, days_back=90)
    print()
    sync_all_customers(limit=100)
    print()
    sync_all_checkout_sessions(limit=100, days_back=90)
    print()
    sync_all_payouts(limit=100, days_back=90)
    
    print()
    print("=" * 60)
    print("Sincronização concluída!")
    print("=" * 60)
