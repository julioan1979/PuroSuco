# 🔄 Atualização Automática via Webhooks

## Status Atual
❌ **Sincronização Manual** - Requer executar scripts Python manualmente  
✅ **Solução**: Usar o webhook oficial (Railway) para atualização automática em tempo real

## Como Ativar Sincronização Automática (Fluxo Oficial)

### Endpoint Oficial (Produção)

- **URL**: `https://stripe-webhook-airtable-production.up.railway.app/stripe/webhook`
- **Repositório**: https://github.com/julioan1979/stripe-webhook-airtable
- O serviço usa `performUpsert` por **event_id**/**charge_id**, evitando duplicados.
- Scripts Python completam dados faltantes (PDF/QR/recibos) sem criar duplicados.



**Em produção:**

1. Acesse: https://dashboard.stripe.com/webhooks
2. Clique em **"Add endpoint"**

4. **Eventos a ouvir**:
   - ✅ `charge.succeeded` - Pagamento bem-sucedido
   - ✅ `charge.failed` - Pagamento falhou
   - ✅ `charge.updated` - Pagamento atualizado
   - ✅ `checkout.session.completed` - Checkout finalizado
   - ✅ `customer.created` - Cliente criado
   - ✅ `customer.updated` - Cliente atualizado
   - ✅ `payout.paid` - Transferência paga
   - ✅ `payout.updated` - Transferência atualizada



## Fluxo de Atualização Automática

```
Pagamento no Stripe
       ↓
Stripe envia webhook
       ↓
stripe-webhook-airtable (Railway) recebe
       ↓
performUpsert (event_id / charge_id)
       ↓
Sincroniza para Airtable
       ↓

```

## Tabelas que Atualizam Automaticamente

| Tabela | Evento Stripe | Quando Atualiza |
|--------|---------------|-----------------|
| **Charges** | `charge.succeeded` | Pagamento aprovado |
| **Charges** | `charge.failed` | Pagamento falhou |
| **Charges** | `charge.updated` | Status do charge mudou |
| **Checkout_Sessions** | `checkout.session.completed` | Checkout finalizado |
| **Customers** | `customer.created` | Novo cliente |
| **Customers** | `customer.updated` | Dados do cliente alterados |
| **Payouts** | `payout.paid` | Transferência paga |
| **Payouts** | `payout.updated` | Status da transferência mudou |
| **Logs** | Todos os eventos | Sempre registra |

> **Observação:** A geração de Tickets/QRCodes/PDFs é feita por processos Python (ex.: `stripe_airtable_sync.py`), não diretamente pelo webhook Node.

## Monitoramento

**Ver logs em tempo real:**
- Use os logs do serviço no Railway.

## Teste de Webhook

**Enviar evento de teste:**
```bash
# Via Stripe CLI
stripe trigger charge.succeeded

# Via Dashboard do Stripe
# https://dashboard.stripe.com/webhooks → Selecione webhook → "Send test webhook"
```

**Verificar no Airtable:**
1. Abra a tabela **Charges** no Airtable
2. Verifique se o novo registro apareceu
3. Confira a tabela **Logs** para detalhes

---

## Histórico / Deprecated

- **Legacy**: `server.js`, `webhook_server.py` e `airtable_automation_webhook.js`.
- Evite ativar esses fluxos junto com o webhook oficial para não gerar **dupla ingestão**.

### Desenvolvimento local (legacy)

1. **Instale Stripe CLI**:
   ```bash
   # Windows
   scoop install stripe
   
   # Mac
   brew install stripe/stripe-cli/stripe
   
   # Linux
   wget -O stripe.tar.gz https://github.com/stripe/stripe-cli/releases/download/v1.19.4/stripe_1.19.4_linux_x86_64.tar.gz
   tar -xvf stripe.tar.gz
   ```

2. **Login no Stripe CLI**:
   ```bash
   stripe login
   ```

3. **Encaminhar webhooks para localhost**:
   ```bash
   stripe listen --forward-to localhost:5000/webhook
   ```

4. **Teste o webhook**:
   ```bash
   stripe trigger charge.succeeded
   ```

## Sincronização Manual vs Automática

### Manual (atual)
```bash
python sync_data_to_airtable.py  # Executa quando você quiser
```
- ✅ Controle total
- ❌ Requer execução manual
- ❌ Delay entre pagamento e registro

### Automática (com webhooks)
```bash
# Fluxo oficial: endpoint no Railway (sem processo local)
```
- ✅ Tempo real (< 1 segundo)
- ✅ Sem intervenção manual


## Problemas Comuns

### ❌ Webhook não recebe eventos
**Solução:**
1. Confirme URL correta no Stripe Dashboard
2. Teste com Stripe CLI: `stripe trigger charge.succeeded`
3. Verifique logs no Railway

### ❌ Erro de assinatura inválida
**Solução:**
1. Copie o **signing secret** correto do Stripe Dashboard
2. Atualize `STRIPE_WEBHOOK_SECRET` no serviço Railway
3. Reenvie o evento de teste

### ❌ Eventos processados mas não sincronizam
**Solução:**
1. Verifique logs: erros de Airtable?
2. Confirme `Airtable_Base_ID` está correto
3. Teste sync manual: `python -c "from sync_data_to_airtable import sync_all_charges; sync_all_charges(limit=1)"`

## Custos

- **Stripe Webhooks**: ✅ GRÁTIS
- **Servidor**: Depende da hospedagem
  - Heroku Free Tier: ✅ GRÁTIS
  - VPS básico: ~€5/mês
  - Docker local: ✅ GRÁTIS

## Segurança

- ✅ Assinatura verificada (HMAC)
- ✅ HTTPS em produção
- ✅ Validação de BASE_ID
- ✅ Logs de todas as requisições

---

**Com webhooks configurados, suas tabelas Airtable serão atualizadas automaticamente em tempo real! 🚀**
