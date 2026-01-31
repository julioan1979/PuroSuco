# Documentação da API

## Módulos Principais

### 📦 airtable_client.py

Cliente para interação com Airtable API.

#### `get_airtable_config()`
Obtém e valida credenciais do Airtable.

**Returns:**
- `tuple[str, str]`: (api_key, base_id)

**Raises:**
- `ValueError`: Se credenciais ausentes ou BASE_ID incorreto

**Exemplo:**
```python
from airtable_client import get_airtable_config

api_key, base_id = get_airtable_config()
# base_id é validado contra EXPECTED_BASE_ID
```

#### `upsert_record(table, fields, merge_on=None)`
Cria ou atualiza registro no Airtable.

**Parameters:**
- `table` (str): Nome da tabela
- `fields` (dict): Campos do registro
- `merge_on` (str, optional): Campo para merge (upsert)

**Returns:**
- `dict`: Resposta da API do Airtable

**Exemplo:**
```python
from airtable_client import upsert_record

fields = {
    "charge_id": "ch_xxxxx",
    "amount": 15.00,
    "status": "succeeded"
}
upsert_record("Charges", fields, merge_on="charge_id")
```

#### `list_tables()`
Lista todas as tabelas da base.

**Returns:**
- `dict`: Tabelas e seus metadados

---

### 💳 stripe_airtable_sync.py

Funções de sincronização Stripe → Airtable.

#### `sync_charge_to_airtable(charge, auto_generate_ticket=False)`
Sincroniza um charge do Stripe para Airtable.

**Parameters:**
- `charge` (dict): Objeto charge do Stripe
- `auto_generate_ticket` (bool): Gerar ticket automaticamente

**Returns:**
- `bool`: True se sucesso, False se erro

**Exemplo:**
```python
import stripe
from stripe_airtable_sync import sync_charge_to_airtable

charge = stripe.Charge.retrieve("ch_xxxxx")
sync_charge_to_airtable(charge, auto_generate_ticket=True)
```

#### `sync_customer_to_airtable(customer_id, name, email, phone, address=None)`
Sincroniza dados de cliente.

**Parameters:**
- `customer_id` (str): ID do cliente Stripe
- `name` (str): Nome do cliente
- `email` (str): Email do cliente
- `phone` (str): Telefone do cliente
- `address` (dict, optional): Endereço

**Returns:**
- `bool`: Sucesso da operação

#### `sync_checkout_session_to_airtable(session)`
Sincroniza sessão de checkout.

**Parameters:**
- `session` (dict): Objeto CheckoutSession do Stripe

**Returns:**
- `bool`: Sucesso da operação

#### `sync_payout_to_airtable(payout)`
Sincroniza payout/transferência.

**Parameters:**
- `payout` (dict): Objeto Payout do Stripe

**Returns:**
- `bool`: Sucesso da operação

#### `generate_ticket_for_charge(charge_id, auto_retrieve=True)`
Gera ticket PDF para um charge.

**Parameters:**
- `charge_id` (str): ID do charge
- `auto_retrieve` (bool): Buscar charge no Stripe automaticamente

**Returns:**
- `bool`: Sucesso da geração

---

### 📝 app_logger.py

Sistema de logging centralizado.

#### `log_action(module, action, status, message=None, level=LOG_LEVEL_INFO, ...)`
Registra uma ação no sistema.

**Parameters:**
- `module` (str): Módulo que executou a ação
- `action` (str): Nome da ação
- `status` (str): "success", "error", "warning"
- `message` (str, optional): Mensagem descritiva
- `level` (str): Nível do log (INFO, ERROR, WARNING, DEBUG)
- `user_id` (str, optional): ID do usuário
- `object_type` (str, optional): Tipo de objeto afetado
- `object_id` (str, optional): ID do objeto
- `error_details` (str, optional): Detalhes do erro

**Returns:**
- `str`: UUID do log criado

**Exemplo:**
```python
from app_logger import log_action, LOG_LEVEL_ERROR

log_action(
    module="sync",
    action="sync_charge",
    status="error",
    message="Falha ao sincronizar charge",
    level=LOG_LEVEL_ERROR,
    object_id="ch_xxxxx"
)
```

#### `log_sync(object_type, object_id, status, message=None)`
Atalho para logs de sincronização.

#### `log_pdf_generation(ticket_id, status, file_size=None, error=None)`
Atalho para logs de geração de PDF.

---

### 📄 pdf_generator.py

Geração de tickets em PDF.

#### `generate_ticket_pdf(ticket_id, customer_name, customer_email, ...)`
Gera um ticket em PDF com QR code.

**Parameters:**
- `ticket_id` (str): UUID do ticket
- `customer_name` (str): Nome do cliente
- `customer_email` (str): Email do cliente
- `ticket_type` (str): Tipo de ticket
- `quantity` (int): Quantidade
- `price` (float): Preço
- `currency` (str): Moeda (EUR, USD, etc)
- `items` (list): Lista de itens do ticket

**Returns:**
- `tuple[bytes, str]`: (pdf_bytes, pdf_base64)

**Exemplo:**
```python
from pdf_generator import generate_ticket_pdf

pdf_bytes, pdf_base64 = generate_ticket_pdf(
    ticket_id="uuid-xxxx",
    customer_name="João Silva",
    customer_email="joao@exemplo.com",
    ticket_type="VIP",
    quantity=1,
    price=15.00,
    currency="EUR",
    items=[{"description": "Entrada VIP", "quantity": 1, "amount": 15.00}]
)
```

#### `generate_qrcode_data(ticket_id, customer_email)`
Gera dados para QR code.

**Returns:**
- `str`: String codificada para QR code

---

## Fluxo de Dados

```
Stripe Payment
    ↓
sync_charge_to_airtable()
    ↓
Airtable (Charges table)
    ↓
generate_ticket_for_charge() [opcional]
    ↓
PDF + QR Code
    ↓
Airtable (Tickets + QRCodes tables)
```

## Webhooks

Para receber eventos do Stripe em tempo real:

```python
# Endpoint webhook (exemplo com Flask)
@app.route('/webhook', methods=['POST'])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    
    event = stripe.Webhook.construct_event(
        payload, sig_header, WEBHOOK_SECRET
    )
    
    if event['type'] == 'charge.succeeded':
        charge = event['data']['object']
        sync_charge_to_airtable(charge, auto_generate_ticket=True)
    
    return {'status': 'success'}
```

## Erros Comuns

### ValueError: BASE_ID INCORRETO
```python
# Causa: BASE_ID no .env não corresponde ao esperado
# Solução: Verifique Airtable_Base_ID=apppvZnFTV6a33RUf
```

### HTTPError 403 Forbidden
```python
# Causa: API Key sem permissões para a base
# Solução: Crie novo token com acesso à base correta
```

### HTTPError 422 Unprocessable Entity
```python
# Causa: Campos faltando no Airtable
# Solução: Execute python apply_airtable_schema.py
```

## Tipos de Retorno

### Charge (Stripe)
```python
{
    "id": "ch_xxxxx",
    "amount": 1500,  # em centavos
    "currency": "eur",
    "status": "succeeded",
    "customer": "cus_xxxxx",
    "billing_details": {
        "email": "cliente@exemplo.com",
        "name": "João Silva"
    }
}
```

### Record (Airtable)
```python
{
    "id": "recXXXXX",
    "createdTime": "2026-01-31T12:00:00.000Z",
    "fields": {
        "charge_id": "ch_xxxxx",
        "amount": 15.00,
        "status": "succeeded"
    }
}
```
