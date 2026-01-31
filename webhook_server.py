#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Webhook endpoint para receber eventos do Stripe em tempo real.
Sincroniza automaticamente para Airtable quando pagamentos ocorrem.
"""

import os
import sys
from dotenv import load_dotenv
from flask import Flask, request, jsonify
import stripe

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
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

if not STRIPE_API_KEY or not WEBHOOK_SECRET:
    print("ERRO: STRIPE_API_KEY e STRIPE_WEBHOOK_SECRET são obrigatórias")
    sys.exit(1)

set_stripe_key(STRIPE_API_KEY)
stripe.api_key = STRIPE_API_KEY

app = Flask(__name__)


@app.route('/webhook', methods=['POST'])
def stripe_webhook():
    """
    Endpoint que recebe eventos do Stripe via webhook.
    Sincroniza automaticamente para Airtable.
    """
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')

    # Validar assinatura do webhook
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, WEBHOOK_SECRET
        )
    except ValueError as e:
        log_action("webhook", "validate_signature", "error", 
                   error_details=f"Payload inválido: {str(e)}")
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.error.SignatureVerificationError as e:
        log_action("webhook", "validate_signature", "error",
                   error_details=f"Assinatura inválida: {str(e)}")
        return jsonify({'error': 'Invalid signature'}), 400

    # Processar evento
    event_type = event['type']
    data_object = event['data']['object']

    print(f"📥 Webhook recebido: {event_type}")
    log_action("webhook", f"receive_{event_type}", "success", 
               message=f"Evento recebido: {event.get('id')}")

    # Sincronizar baseado no tipo de evento
    try:
        if event_type == 'charge.succeeded':
            charge = data_object
            sync_charge_to_airtable(charge, auto_generate_ticket=True)
            print(f"✅ Charge {charge['id']} sincronizado com ticket gerado")

        elif event_type == 'charge.failed':
            charge = data_object
            sync_charge_to_airtable(charge, auto_generate_ticket=False)
            print(f"⚠️  Charge {charge['id']} falhou - sincronizado sem ticket")

        elif event_type == 'charge.updated':
            charge = data_object
            sync_charge_to_airtable(charge, auto_generate_ticket=False)
            print(f"🔄 Charge {charge['id']} atualizado")

        elif event_type == 'checkout.session.completed':
            session = data_object
            sync_checkout_session_to_airtable(session)
            print(f"✅ Checkout session {session['id']} sincronizado")

        elif event_type == 'customer.created' or event_type == 'customer.updated':
            customer = data_object
            sync_customer_to_airtable(
                customer_id=customer.get('id'),
                name=customer.get('name'),
                email=customer.get('email'),
                phone=customer.get('phone'),
                address=customer.get('address')
            )
            print(f"✅ Customer {customer['id']} sincronizado")

        elif event_type == 'payout.paid' or event_type == 'payout.updated':
            payout = data_object
            sync_payout_to_airtable(payout)
            print(f"✅ Payout {payout['id']} sincronizado")

        else:
            # Logar eventos não tratados
            log_action("webhook", f"unhandled_{event_type}", "warning",
                       message=f"Evento não tratado: {event_type}")
            print(f"ℹ️  Evento não tratado: {event_type}")

    except Exception as e:
        log_action("webhook", f"process_{event_type}", "error",
                   error_details=str(e))
        print(f"❌ Erro ao processar {event_type}: {str(e)}")
        return jsonify({'error': 'Processing failed'}), 500

    return jsonify({'status': 'success'}), 200


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({'status': 'healthy', 'service': 'stripe-webhook'}), 200


@app.route('/', methods=['GET'])
def index():
    """Index page."""
    return jsonify({
        'service': 'PuroSuco Stripe Webhook',
        'version': '1.0.0',
        'endpoints': {
            '/webhook': 'POST - Recebe eventos do Stripe',
            '/health': 'GET - Health check'
        }
    }), 200


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    print("=" * 60)
    print("🚀 SERVIDOR WEBHOOK INICIADO")
    print("=" * 60)
    print(f"📍 Porta: {port}")
    print(f"🔗 Webhook URL: http://localhost:{port}/webhook")
    print(f"💚 Health Check: http://localhost:{port}/health")
    print("=" * 60)
    print("\n⚠️  Configure este endpoint no Stripe Dashboard:")
    print("   https://dashboard.stripe.com/webhooks")
    print("\n📋 Eventos recomendados:")
    print("   - charge.succeeded")
    print("   - charge.failed")
    print("   - charge.updated")
    print("   - checkout.session.completed")
    print("   - customer.created")
    print("   - customer.updated")
    print("   - payout.paid")
    print("   - payout.updated")
    print("\n" + "=" * 60)
    
    # Modo debug apenas em desenvolvimento
    debug_mode = os.getenv('FLASK_ENV') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
