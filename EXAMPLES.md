# 📚 Exemplos de Uso - PuroSuco

Guia com exemplos práticos de como usar as principais funcionalidades do PuroSuco.

---

## 1️⃣ Sincronizar um Charge do Stripe para Airtable

```python
import stripe
from stripe_airtable_sync import sync_charge_to_airtable, set_stripe_key
from dotenv import load_dotenv
import os

load_dotenv()
set_stripe_key(os.getenv("STRIPE_API_KEY"))

# Buscar um charge específico
charge = stripe.Charge.retrieve("ch_xxxxx")

# Sincronizar para Airtable (com ticket automático)
success = sync_charge_to_airtable(charge, auto_generate_ticket=True)

if success:
    print(f"✅ Charge {charge['id']} sincronizado com sucesso!")
else:
    print("❌ Erro ao sincronizar")
```

---

## 2️⃣ Sincronizar Dados de Cliente

```python
from stripe_airtable_sync import sync_customer_to_airtable

# Sincronizar dados de cliente
success = sync_customer_to_airtable(
    customer_id="cus_xxxxx",
    name="João Silva",
    email="joao@exemplo.com",
    phone="+351 912 345 678",
    address={
        "street": "Rua do Exemplo, 123",
        "city": "Lisboa",
        "country": "PT",
        "postal_code": "1000-001"
    }
)

if success:
    print("✅ Cliente sincronizado!")
else:
    print("❌ Erro ao sincronizar cliente")
```

---

## 3️⃣ Gerar Ticket PDF com QR Code

```python
from pdf_generator import generate_ticket_pdf
from datetime import datetime

# Gerar ticket
ticket_data = {
    "ticket_id": "uuid-xxxx-yyyy",
    "customer_name": "João Silva",
    "customer_email": "joao@exemplo.com",
    "ticket_type": "VIP",
    "quantity": 2,
    "price": 25.00,
    "currency": "EUR",
    "items": [
        {
            "description": "Entrada VIP - Niver Bia 2026",
            "quantity": 2,
            "amount": 25.00
        }
    ]
}

# Gerar PDF
pdf_bytes, pdf_base64 = generate_ticket_pdf(**ticket_data)

# Salvar localmente
with open(f"ticket_{ticket_data['ticket_id']}.pdf", "wb") as f:
    f.write(pdf_bytes)

print(f"✅ Ticket PDF gerado: {len(pdf_bytes)} bytes")
```

---

## 4️⃣ Validar QR Code de Entrada

```python
from qrcode_manager import validate_qrcode, mark_ticket_as_validated

# Simular scan de QR code (formato: TICKET:ticket_id:email)
qr_data = "TICKET:uuid-xxxx:joao@exemplo.com"

# Validar
result = validate_qrcode(qr_data, validated_by="Segurança - João")

if result["success"]:
    print(f"✅ Ingresso válido!")
    print(f"   Ticket ID: {result['ticket_id']}")
    print(f"   Validado em: {result['validated_at']}")
    
    # Marcar como validado no Airtable
    mark_ticket_as_validated(result['ticket_id'], validated_by="Segurança - João")
else:
    print(f"❌ Erro: {result['error']}")
```

---

## 5️⃣ Buscar Dados de Ticket

```python
from qrcode_manager import get_ticket_data

# Buscar ticket pelo ID
ticket_id = "uuid-xxxx"
ticket = get_ticket_data(ticket_id)

if ticket["success"]:
    print(f"✅ Ticket encontrado:")
    print(f"   Status: {ticket['status']}")
    print(f"   Cliente: {ticket['customer_name']}")
    print(f"   Email: {ticket['customer_email']}")
    print(f"   Validado por: {ticket['validated_by']}")
else:
    print(f"❌ Ticket não encontrado: {ticket['error']}")
```

---

## 6️⃣ Baixar PDF de Ticket

```python
from qrcode_manager import download_ticket_pdf

ticket_id = "uuid-xxxx"
pdf_bytes, filename = download_ticket_pdf(ticket_id)

if pdf_bytes:
    # Salvar arquivo
    with open(filename, "wb") as f:
        f.write(pdf_bytes)
    print(f"✅ PDF salvo: {filename}")
else:
    print("❌ PDF não encontrado")
```

---

## 7️⃣ Obter Estatísticas de Ingressos

```python
from qrcode_manager import get_ticket_statistics

stats = get_ticket_statistics()

if stats["success"]:
    print(f"📊 Estatísticas de Ingressos:")
    print(f"   Total: {stats['total_tickets']}")
    print(f"   Validados: {stats['validated']}")
    print(f"   Pendentes: {stats['pending']}")
    print(f"   % Validado: {stats['percentage_validated']}%")
else:
    print(f"❌ Erro: {stats['error']}")
```

---

## 8️⃣ Criar/Atualizar Registro no Airtable

```python
from airtable_client import upsert_record

# Criar ou atualizar registro
fields = {
    "charge_id": "ch_xxxxx",
    "amount": 25.00,
    "currency": "EUR",
    "status": "succeeded",
    "customer_email": "joao@exemplo.com"
}

# Usar "charge_id" como chave de merge (upsert)
result = upsert_record("Charges", fields, merge_on="charge_id")

if result:
    print(f"✅ Registro criado/atualizado")
    print(f"   Record ID: {result['records'][0]['id']}")
else:
    print("❌ Erro ao criar/atualizar")
```

---

## 9️⃣ Registar Ação no Sistema de Logs

```python
from app_logger import log_action, LOG_LEVEL_ERROR

# Registar ação bem-sucedida
log_action(
    module="payment",
    action="process_charge",
    status="success",
    message="Charge processado com sucesso",
    object_type="Charge",
    object_id="ch_xxxxx"
)

# Registar erro
log_action(
    module="payment",
    action="process_charge",
    status="error",
    message="Falha ao processar charge",
    level=LOG_LEVEL_ERROR,
    object_type="Charge",
    object_id="ch_yyyyy",
    error_details="Cartão recusado: funds_insufficient"
)
```

---

## 🔟 Listar Tabelas Airtable

```python
from airtable_client import list_tables

tables = list_tables()

print("📋 Tabelas disponíveis:")
for table in tables["tables"]:
    print(f"   - {table['name']} (ID: {table['id']})")
    print(f"     Fields: {len(table['fields'])}")
```

---

## 1️⃣1️⃣ Exemplo: Processar Webhook Stripe Completo

```python
import stripe
from stripe_airtable_sync import (
    sync_charge_to_airtable,
    sync_customer_to_airtable,
    sync_checkout_session_to_airtable
)
from app_logger import log_action

def handle_charge_succeeded(event):
    """Processar evento de charge bem-sucedido"""
    try:
        charge = event["data"]["object"]
        
        # 1. Sincronizar charge
        sync_charge_to_airtable(charge, auto_generate_ticket=True)
        
        # 2. Sincronizar dados de cliente
        if charge.get("customer"):
            sync_customer_to_airtable(
                customer_id=charge["customer"],
                email=charge.get("billing_details", {}).get("email"),
                name=charge.get("billing_details", {}).get("name")
            )
        
        # 3. Registar no log
        log_action(
            module="webhook",
            action="charge_succeeded",
            status="success",
            message=f"Charge {charge['id']} processado",
            object_type="Charge",
            object_id=charge["id"]
        )
        
        print(f"✅ Webhook processado: {charge['id']}")
        return True
        
    except Exception as e:
        log_action(
            module="webhook",
            action="charge_succeeded",
            status="error",
            message="Falha ao processar webhook",
            object_type="Charge",
            object_id=event.get("id"),
            error_details=str(e)
        )
        print(f"❌ Erro: {str(e)}")
        return False
```

---

## 1️⃣2️⃣ Teste de Integração Completa

```python
#!/usr/bin/env python3
"""
Script de teste para validar toda a integração
"""
import os
from dotenv import load_dotenv
from airtable_client import get_airtable_config, list_tables
from qrcode_manager import get_ticket_statistics
from app_logger import log_action

load_dotenv()

print("🧪 Testando integração PuroSuco...")
print()

# 1. Validar Airtable
try:
    api_key, base_id = get_airtable_config()
    print(f"✅ Airtable configurado: {base_id}")
except Exception as e:
    print(f"❌ Erro Airtable: {e}")
    exit(1)

# 2. Listar tabelas
try:
    tables = list_tables()
    print(f"✅ Tabelas encontradas: {len(tables['tables'])}")
    for t in tables['tables']:
        print(f"   - {t['name']}")
except Exception as e:
    print(f"❌ Erro ao listar tabelas: {e}")
    exit(1)

# 3. Testar sistema de logs
try:
    log_action("test", "integration_check", "success", "Teste de integração executado")
    print("✅ Sistema de logs funcional")
except Exception as e:
    print(f"❌ Erro sistema de logs: {e}")

# 4. Testar estatísticas
try:
    stats = get_ticket_statistics()
    if stats["success"]:
        print(f"✅ Ingressos: {stats['total_tickets']} (validados: {stats['validated']})")
    else:
        print(f"⚠️  Sem ingressos ainda")
except Exception as e:
    print(f"❌ Erro ao obter estatísticas: {e}")

print()
print("🎉 Teste concluído!")
```

---

## 💡 Dicas de Debugging

### Ver logs no console
```python
from app_logger import LOG_LEVEL_DEBUG

log_action(
    module="debug",
    action="test",
    status="success",
    level=LOG_LEVEL_DEBUG,
    message="Informação de debug"
)
```

### Validar formato de QR Code
```python
qr_data = "TICKET:meu-uuid:email@example.com"
assert qr_data.startswith("TICKET:"), "Formato de QR inválido"
```

### Testar conexão Airtable
```bash
python -c "
from airtable_client import get_airtable_config, list_tables
api_key, base_id = get_airtable_config()
print(f'Base ID: {base_id}')
print(f'Tabelas: {len(list_tables()[\"tables\"])}')
"
```

---

**Mais exemplos em desenvolvimento... Contribuições bem-vindas! 🤝**
