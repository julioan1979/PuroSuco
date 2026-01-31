# 📋 Como Sincronizar Dados com Airtable

## Pré-requisitos
- Credenciais Airtable definidas em `.env`
- Base criada em Airtable
- Tabelas: `Charges`, `Customers`, `Checkout_Sessions`, `Stripe_Events`, `Tickets`, `QRCodes`, `Logs`

## Método 1: Sincronização Automática (Streamlit)
1. Abra o app: `streamlit run stripe_streamlit_app.py`
2. Os dados sincronizam automaticamente ao carregar (últimos 50 charges + 20 clientes)
3. Menu "Airtable" → Botões para sincronizar em lote

## Método 2: Script Manual
```bash
python sync_data_to_airtable.py
```
Sincroniza:
- Últimos 100 charges (90 dias)
- 100 clientes
- Últimas 100 checkout sessions (90 dias)

## Método 3: Criar Tabelas no Airtable Manualmente
Se a API falhar, crie as tabelas manualmente usando `airtable_schema.json`:

### Tabela: Charges
- `charge_id` (Text, Primary)
- `created_at` (DateTime)
- `status` (Text)
- `amount` (Number)
- `currency` (Text)
- `customer_id` (Text)
- `customer_email` (Email)
- `billing_name` (Text)
- `receipt_url` (URL)
- ... (ver schema completo em airtable_schema.json)

### Tabela: Customers
- `customer_id` (Text, Primary)
- `name` (Text)
- `email` (Email)
- `phone` (Text)

### Tabela: Tickets
- `ticket_id` (Text, Primary)
- `charge_id` (Text)
- `customer_email` (Email)
- `pdf_data` (Long Text, Base64)
- `status` (Text)

### Tabela: Logs
- `log_id` (Text, Primary)
- `timestamp` (DateTime)
- `level` (Text)
- `module` (Text)
- `action` (Text)
- `message` (Long Text)

## Verificação
1. Abra base Airtable
2. Verifique tabela "Charges" - deve ter registos
3. Verifique tabela "Logs" - deve mostrar operações

## Troubleshooting

### Erro: "422 Client Error"
Significa que a API Airtable não aceitou o schema. Solução:
- Crie as tabelas manualmente em Airtable
- O script `create_airtable_schema.py` só funciona se a base suporta API de criação de tabelas

### Sem dados em Airtable
- Verifique credenciais `.env`:
  - `AIRTABLE_API_KEY`
  - `AIRTABLE_BASE_ID`
- Execute `python sync_data_to_airtable.py`
- Ou use botão "Sincronizar Charges" em Airtable menu

### Bilhetes não aparecem
- Execute "Gerar Bilhete" em menu "Bilhetes"
- Verifique tabela "Tickets" em Airtable
