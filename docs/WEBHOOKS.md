# 🔄 Atualização Automática via Webhooks

## Status Atual
❌ **Sincronização Manual** - Requer executar scripts Python manualmente  
✅ **Solução**: Configurar webhooks do Stripe para atualização automática em tempo real

## Como Ativar Sincronização Automática

### 1. Instalar dependências Node.js (servidor webhook)
```bash
npm install
```

### 2. Adicionar WEBHOOK_SECRET ao .env
```env
STRIPE_WEBHOOK_SECRET=whsec_xxxxx
```

### 3. Iniciar Servidor Webhook
```bash
npm start
```

Servidor iniciará em: `http://localhost:8080/stripe/webhook`

### 4. Configurar Stripe Dashboard

**Em ambiente de desenvolvimento (localhost):**

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
   stripe listen --forward-to localhost:8080/stripe/webhook
   ```

4. **Copie o signing secret** que aparece e adicione ao `.env`:
   ```env
   STRIPE_WEBHOOK_SECRET=whsec_xxxxx
   ```

5. **Teste o webhook**:
   ```bash
   # Em outro terminal
   stripe trigger charge.succeeded
   ```

**Em produção:**

1. Acesse: https://dashboard.stripe.com/webhooks
2. Clique em **"Add endpoint"**
3. **Endpoint URL**: `https://seu-dominio.com/stripe/webhook` (ou o URL do Railway, ex.: `https://seu-app.up.railway.app/stripe/webhook`)
4. **Eventos a ouvir**:
   - ✅ `charge.succeeded` - Pagamento bem-sucedido
   - ✅ `charge.failed` - Pagamento falhou
   - ✅ `charge.updated` - Pagamento atualizado
   - ✅ `checkout.session.completed` - Checkout finalizado
   - ✅ `customer.created` - Cliente criado
   - ✅ `customer.updated` - Cliente atualizado
   - ✅ `payout.paid` - Transferência paga
   - ✅ `payout.updated` - Transferência atualizada

5. Copie o **Signing secret** e adicione ao `.env`

### 5. Deploy do Webhook

**Opção A: Docker**
```yaml
# docker-compose.yml
version: '3.8'
services:
  webhook:
    build: .
    ports:
         - "8080:8080"
    environment:
      - STRIPE_API_KEY=${STRIPE_API_KEY}
      - STRIPE_WEBHOOK_SECRET=${STRIPE_WEBHOOK_SECRET}
         - AIRTABLE_PAT=${AIRTABLE_PAT}
         - AIRTABLE_BASE_ID=apppvZnFTV6a33RUf
    restart: unless-stopped
```

```dockerfile
# Dockerfile
FROM node:20-slim
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install --omit=dev
COPY . .
CMD ["node", "server.js"]
```

**Opção B: Heroku**
```bash
# Procfile
web: node server.js
```

**Opção C: VPS (Ubuntu + Supervisor)**
```ini
# /etc/supervisor/conf.d/webhook.conf
[program:purosuco-webhook]
directory=/var/www/purosuco
command=/usr/bin/node /var/www/purosuco/server.js
user=www-data
autostart=true
autorestart=true
stderr_logfile=/var/log/purosuco/webhook-err.log
stdout_logfile=/var/log/purosuco/webhook-out.log
environment=PORT="8080"
```

```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start purosuco-webhook
```

**Nginx reverse proxy:**
```nginx
# /etc/nginx/sites-available/webhook
server {
   listen 80;
    server_name webhook.seu-dominio.com;

    location / {
      proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Fluxo de Atualização Automática

```
Pagamento no Stripe
       ↓
Stripe envia webhook
       ↓
server.js recebe
       ↓
Valida assinatura
       ↓
Identifica tipo de evento
       ↓
Sincroniza para Airtable
       ↓
Processo Python gera tickets/PDFs (ex.: stripe_airtable_sync.py)
       ↓
Tabelas atualizadas automaticamente!
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
```bash
# Desenvolvimento
npm start

# Produção (Docker)
docker-compose logs -f webhook

# Produção (Supervisor)
sudo tail -f /var/log/purosuco/webhook-out.log
```

**Health check:**
```bash
curl http://localhost:8080/health
# Resposta: {"status":"healthy","service":"stripe-webhook"}
```

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
npm start  # Executa 24/7
```
- ✅ Tempo real (< 1 segundo)
- ✅ Sem intervenção manual
- ⚠️ Requer servidor rodando

## Problemas Comuns

### ❌ Webhook não recebe eventos
**Solução:**
1. Verifique se servidor está rodando: `curl http://localhost:8080/health`
2. Confirme URL correta no Stripe Dashboard
3. Teste com Stripe CLI: `stripe trigger charge.succeeded`

### ❌ Erro de assinatura inválida
**Solução:**
1. Copie o **signing secret** correto do Stripe Dashboard
2. Atualize `STRIPE_WEBHOOK_SECRET` no `.env`
3. Reinicie o servidor webhook

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
