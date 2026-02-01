# 🎉 PuroSuco - Gerenciador de Ingressos Online

**Puro Suco Niver Bia 2026**

Sistema completo de gerenciamento de ingressos/tickets para eventos, integrando pagamentos via Stripe com banco de dados Airtable, geração automática de tickets em PDF com QR codes e validação de entrada.

---

## ✨ Funcionalidades

✅ **Checkout Online** - Stripe Checkout integrado  
✅ **Gerenciamento de Ingressos** - Dashboard Streamlit interativo  
✅ **Geração de Tickets PDF** - Com QR codes únicos  
✅ **Validação de Entrada** - Scan de QR codes  
✅ **Sincronização Automática** - Stripe ↔ Airtable em tempo real  
✅ **Webhooks** - Eventos em tempo real  
✅ **Dashboard de Analytics** - Métricas e gráficos  
✅ **Sistema de Logs** - Auditoria completa  

---

## 🏗️ Arquitetura

```
┌─────────────────┐
│  Stripe Checkout │
└────────┬────────┘
         │ Webhook
         ▼
┌────────────────────────────────────────────────────────────┐
│ stripe-webhook-airtable (Railway)                           │
│ https://stripe-webhook-airtable-production.up.railway.app   │
│ /stripe/webhook                                             │
└────────┬───────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│  Airtable (banco de dados)  │
│  - Charges                  │
│  - Customers                │
│  - Tickets                  │
│  - Logs                     │
└────────┬────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│ Python enrichment scripts   │
│ stripe_airtable_sync.py     │
│ stripe_receipt_scraper.py   │
└─────────────────────────────┘

┌────────────────────────────┐
│ stripe_streamlit_app.py    │ ◄─ Dashboard
└────────────────────────────┘
```

---

## 🚀 Quick Start

### Pré-requisitos
- Python 3.13+
- Conta Stripe (produção)
- Base Airtable configurada
- Virtual environment

### Instalação

```bash
# Clone o repositório
git clone https://github.com/julioan1979/purosuco.git
cd purosuco

# Crie e ative ambiente virtual
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Instale dependências
pip install -r requirements.txt

# Configure variáveis de ambiente
cp .env.example .env
# Edite .env com suas credenciais
```

### Execução

```bash
# Terminal: Inicie o dashboard Streamlit
streamlit run stripe_streamlit_app.py
```

O dashboard estará disponível em `http://localhost:8501`

**Webhook oficial (produção)**: configure no Stripe o endpoint  
`https://stripe-webhook-airtable-production.up.railway.app/stripe/webhook` (repo: https://github.com/julioan1979/stripe-webhook-airtable).

---

## 📋 Estrutura do Projeto

```
purosuco/
├── stripe_streamlit_app.py      # Dashboard principal
├── webhook_server.py            # (Legacy) Webhook Stripe local
├── stripe_airtable_sync.py      # Sincronização de dados
├── pdf_generator.py             # Geração de tickets PDF
├── qrcode_manager.py            # Gerenciamento de QR codes
├── airtable_client.py           # Cliente Airtable API
├── app_logger.py                # Sistema de logs
├── requirements.txt             # Dependências Python
├── .env                         # Variáveis de ambiente
├── README.md                    # Este arquivo
└── docs/
    ├── API.md                   # Documentação da API
    ├── DEPLOYMENT.md            # Guias de deploy
    ├── WEBHOOKS.md              # Configuração de webhooks
    └── SYNC_GUIDE.md            # Guia de sincronização
```

---

## 📚 Documentação

- **[API.md](docs/API.md)** - Documentação completa dos módulos
- **[DEPLOYMENT.md](docs/DEPLOYMENT.md)** - Deploy em produção (Docker, VPS, Streamlit Cloud)
- **[WEBHOOKS.md](docs/WEBHOOKS.md)** - Configuração de webhooks Stripe
- **[SYNC_GUIDE.md](SYNC_GUIDE.md)** - Guia passo-a-passo de sincronização

---

## 🌐 Webhook Oficial (Produção)

- **Endpoint em produção**: `https://stripe-webhook-airtable-production.up.railway.app/stripe/webhook`
- **Repositório responsável**: https://github.com/julioan1979/stripe-webhook-airtable

O serviço oficial recebe os eventos da Stripe e faz `performUpsert` por `event_id`/`charge_id`, garantindo deduplicação. Depois, os scripts Python complementam campos que faltam (PDF, recibo, QR) sem criar duplicados.

---

## 🔧 Configuração do Airtable

### Tabelas Necessárias

1. **Charges** - Transações Stripe
2. **Customers** - Dados de clientes
3. **Tickets** - Ingressos gerados (com QR codes)
4. **Checkout_Sessions** - Sessões de compra
5. **Payouts** - Transferências
6. **Logs** - Auditoria do sistema

Para criar automaticamente, execute:

```bash
python create_airtable_schema.py
```

---

## 🔐 Segurança

⚠️ **IMPORTANTE**: Nunca commite o arquivo `.env` no git!

```bash
# O .gitignore já protege:
.env
.env.local
__pycache__/
.venv/
```

**Variáveis Obrigatórias:**
- `STRIPE_API_KEY` - Chave de API Stripe
- `STRIPE_WEBHOOK_SECRET` - Secret do webhook
- `Airtable_API_Key` - Token de autenticação Airtable
- `Airtable_Base_ID` - ID da base (validado automaticamente)

---

## 📊 Fluxo de Pagamento

```
1. Cliente clica em "Comprar"
   ↓
2. Stripe Checkout (Streamlit)
   ↓
3. Pagamento processado
   ↓
4. Stripe envia webhook
   ↓
5. stripe-webhook-airtable (Railway) recebe e grava no Airtable
   ↓
6. Python scripts enriquecem (PDF/QR + recibos) sem duplicar
   ↓
7. Envia ticket ao cliente
```

---

## 🎫 Validação de Ingressos

No evento, use:

```python
from qrcode_manager import validate_qrcode

result = validate_qrcode("TICKET:uuid-xxxx:email@example.com", 
                        validated_by="João Silva")

if result["success"]:
    print(f"✅ Ingresso válido: {result['ticket_id']}")
else:
    print(f"❌ Erro: {result['error']}")
```

---

## 📈 Estatísticas

Obtenha métricas de ingressos:

```python
from qrcode_manager import get_ticket_statistics

stats = get_ticket_statistics()
print(f"Total de ingressos: {stats['total_tickets']}")
print(f"Validados: {stats['validated']}")
print(f"Pendentes: {stats['pending']}")
```

---

## 🚢 Deploy em Produção

Ver [DEPLOYMENT.md](docs/DEPLOYMENT.md) para:
- ✅ Deploy com Docker
- ✅ Deploy no Streamlit Cloud
- ✅ Deploy em VPS (Ubuntu)
- ✅ Configuração de domínio
- ✅ SSL/HTTPS
- ✅ Monitoramento

---

## 🤝 Contribuição

Ver [CONTRIBUTING.md](CONTRIBUTING.md) para mais detalhes.

---

## 📞 Suporte

Para dúvidas ou problemas:
- Abra uma issue no GitHub
- Consulte a documentação em `/docs`
- Verifique os logs em `app.log`

---

## 📄 Licença

Ver [LICENSE](LICENSE)

---

**Desenvolvido com ❤️ para Niver Bia 2026**
