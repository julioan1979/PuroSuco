# PuroSuco - Sistema de Gestão de Eventos com Stripe e Airtable

Sistema completo de gestão de eventos que integra pagamentos do Stripe com base de dados Airtable, incluindo geração automática de tickets com QR codes e interface web com Streamlit.

## 🚀 Funcionalidades

- **Integração Stripe**: Sincronização automática de charges, customers, checkout sessions e payouts
- **Base de Dados Airtable**: Armazenamento estruturado de todos os dados do evento
- **Geração de Tickets**: Criação automática de tickets em PDF com QR codes únicos
- **Interface Streamlit**: Dashboard web para gestão e visualização de dados
- **Validação de Tickets**: Sistema de picking/validação de tickets via QR code
- **Logs Centralizados**: Sistema completo de logging de todas as operações
- **Blindagem de Segurança**: Validação rigorosa de BASE_ID para prevenir uso de bases incorretas

## 📋 Pré-requisitos

- Python 3.13+
- Conta Stripe (API Key)
- Conta Airtable (Personal Access Token e Base ID)
- Bibliotecas Python (ver `requirements.txt`)

## 🔧 Instalação

1. **Clone o repositório**
```bash
git clone https://github.com/seu-usuario/purosuco.git
cd purosuco
```

2. **Crie um ambiente virtual**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows
```

3. **Instale as dependências**
```bash
pip install -r requirements.txt
```

4. **Configure as variáveis de ambiente**

Crie um arquivo `.env` na raiz do projeto:
```env
# Stripe
STRIPE_API_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Airtable
Airtable_API_Key=pat...
Airtable_Base_ID=apppvZnFTV6a33RUf
```

⚠️ **IMPORTANTE**: Nunca commite o arquivo `.env` no Git!

5. **Configure o schema do Airtable**
```bash
python apply_airtable_schema.py
```

## 📊 Estrutura do Projeto

```
PuroSuco/
├── .env                          # Variáveis de ambiente (não commitar!)
├── airtable_client.py            # Cliente Airtable com validação de segurança
├── stripe_airtable_sync.py       # Funções de sincronização Stripe→Airtable
├── sync_data_to_airtable.py      # Script de sincronização completa
├── apply_airtable_schema.py      # Aplicador de schema do Airtable
├── airtable_schema.json          # Definição do schema das tabelas
├── app_logger.py                 # Sistema de logging centralizado
├── pdf_generator.py              # Gerador de tickets em PDF
├── stripe_streamlit_app.py       # Interface web Streamlit
└── README.md                     # Este arquivo
```

## 🎯 Uso

### Sincronização de Dados do Stripe

**Sincronização completa** (charges, customers, sessions, payouts):
```bash
python sync_data_to_airtable.py
```

**Sincronização individual**:
```python
from sync_data_to_airtable import sync_all_charges, sync_all_payouts

# Sincronizar últimos 30 dias de charges
sync_all_charges(limit=100, days_back=30)

# Sincronizar payouts
sync_all_payouts(limit=100, days_back=365)
```

### Interface Web Streamlit

```bash
streamlit run stripe_streamlit_app.py
```

Acesse: http://localhost:8501

### Geração de Tickets

Os tickets são gerados automaticamente após pagamentos bem-sucedidos ou manualmente:

```python
from stripe_airtable_sync import generate_ticket_for_charge

# Gerar ticket para um charge específico
generate_ticket_for_charge("ch_xxxxx", auto_retrieve=True)
```

## 🔒 Segurança

O sistema implementa **blindagem total** contra uso de bases incorretas:

- Validação rigorosa do `BASE_ID` esperado (`apppvZnFTV6a33RUf`)
- Falha imediata se tentar usar outro BASE_ID
- Sem fallbacks hardcoded que possam causar sincronização errada
- Logs detalhados de todas as operações

### Exemplo de Validação

```python
# Em airtable_client.py
EXPECTED_BASE_ID = "apppvZnFTV6a33RUf"

def get_airtable_config():
    # ... validações ...
    if base_id != EXPECTED_BASE_ID:
        raise ValueError(
            f"❌ ERRO CRÍTICO: BASE_ID INCORRETO!\n"
            f"   BASE_ID encontrado: {base_id}\n"
            f"   BASE_ID esperado: {EXPECTED_BASE_ID}"
        )
```

## 📚 Schema do Airtable

O projeto utiliza as seguintes tabelas:

- **Stripe_Events**: Eventos webhook do Stripe
- **Charges**: Cobranças/pagamentos
- **Payment_Intents**: Intenções de pagamento
- **Checkout_Sessions**: Sessões de checkout
- **Customers**: Clientes
- **Payouts**: Transferências para conta bancária
- **Tickets**: Tickets gerados com PDF
- **QRCodes**: QR codes para validação de tickets
- **Logs**: Logs de todas as operações

Para aplicar ou atualizar o schema:
```bash
python apply_airtable_schema.py
```

## 🧪 Diagnóstico e Manutenção

**Verificar configuração do Airtable**:
```bash
python debug_tables.py
```

**Executar diagnóstico de BASE_ID**:
```bash
python fix_airtable_base.py
```

## 🤝 Contribuindo

1. Fork o projeto
2. Crie uma branch para sua feature (`git checkout -b feature/MinhaFeature`)
3. Commit suas mudanças (`git commit -m 'Adiciona MinhaFeature'`)
4. Push para a branch (`git push origin feature/MinhaFeature`)
5. Abra um Pull Request

## 📝 Changelog

### v1.0.0 (2026-01-31)
- ✅ Integração completa com Stripe API
- ✅ Sincronização automática para Airtable
- ✅ Geração de tickets em PDF com QR codes
- ✅ Interface Streamlit
- ✅ Sistema de logging centralizado
- ✅ Blindagem de segurança para BASE_ID
- ✅ Aplicador automático de schema

## ⚠️ Troubleshooting

### Erro 403 Forbidden
- Verifique se sua `Airtable_API_Key` tem permissões para a base
- Confirme que o token tem acesso à base `apppvZnFTV6a33RUf`

### Erro 422 Unprocessable Entity
- Campos podem estar faltando no Airtable
- Execute `python apply_airtable_schema.py` para criar campos faltantes

### BASE_ID INCORRETO
- O sistema só aceita a base `apppvZnFTV6a33RUf`
- Verifique o arquivo `.env` e corrija o `Airtable_Base_ID`

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

## 👤 Autor

**Julio - PuroSuco**

## 🙏 Agradecimentos

- Stripe API Documentation
- Airtable API Documentation
- Streamlit Framework
- Comunidade Python
