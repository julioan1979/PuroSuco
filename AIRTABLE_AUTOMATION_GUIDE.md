#  Airtable Automation - Guia Completo (Legacy)

## Resumo Executivo

⚠️ **Status**: Este guia é **legacy**. O fluxo oficial agora é:

**Stripe → stripe-webhook-airtable (Railway) → Airtable → scripts Python para enriquecimento**.

### Fluxo Oficial (Recomendado)

- **Endpoint em produção**: `https://stripe-webhook-airtable-production.up.railway.app/stripe/webhook`
- **Repositório responsável**: https://github.com/julioan1979/stripe-webhook-airtable
- O serviço usa `performUpsert` por **event_id**/**charge_id** para deduplicar.
- Os scripts Python complementam campos faltantes (PDF, QR, recibos) sem criar duplicados.

### Por que manter este guia?
Para referência histórica e troubleshooting de uma opção **deprecated** que pode causar **dupla ingestão** se usada junto com o fluxo oficial.

---

## Histórico / Deprecated: Como Configurar a Automation

### Passo 1: Criar Automation no Airtable

1. Abrir base no Airtable
2. Clicar em **"Automations"** (no topo)
3. Clicar **"Create new"**
4. Selecionar **"When webhook received"**
5. Copiar a **WEBHOOK URL** exibida

`
 IMPORTANTE: Guardar a URL - vai precisar para o Stripe!
`

### Passo 2: Adicionar "Run script" Action

1. No Airtable automation, clicar **"Add action"**
2. Selecionar **"Run script"**
3. Na janela de código, apagar o exemplo
4. **COLAR TODO O CÓDIGO** do ficheiro irtable_automation_webhook.js
5. Clicar **"Save"**

### Passo 3: Ativar a Automation

1. Clicar toggle **"On"** (verde)
2. A automation agora está **PRONTA para receber webhooks**

---

## 2. Webhook URL Setup no Stripe (Legacy)

### Passo 1: Ir ao Dashboard Stripe

1. Aceder: https://dashboard.stripe.com/webhooks
2. Clicar **"Add an endpoint"**

### Passo 2: Preencher URL

- **URL**: Cola a webhook URL do Airtable
- **Version**: Deixar default (Stripe API latest)

### Passo 3: Selecionar Eventos

Clicar **"Select events"** e escolher:

-  **charge.succeeded** - Quando charge é processada com sucesso
-  **payment_intent.succeeded** - Quando payment intent é confirmada
-  **checkout.session.completed** - Quando checkout session completa
-  **customer.created** - Novo cliente criado
-  **customer.updated** - Cliente atualizado

### Passo 4: Criar

1. Clicar **"Add endpoint"**
2. Stripe vai começar a enviar webhooks para Airtable

---

## 3. Como Funcionam as Anti-Duplicações (Legacy)

### Problem: Evitar Registos Duplicados

Se a automation receber o MESMO webhook duas vezes, não deve criar dois registos.

### Solution: Verificação por IDs Únicos

`javascript
// Para EVENTOS (audit log)
let existingEvent = await findRecord(tblEvents, "event_id", event.id);
if (!existingEvent) {
    // Só cria se não existe
    await tblEvents.createRecordAsync(...);
}

// Para CHARGES
let existingCharge = await findRecord(tblCharges, "charge_id", chargeId);
if (!existingCharge) {
    // Só cria se charge_id é novo
    await tblCharges.createRecordAsync(...);
}
`

### Campos de Merge (Chaves Únicas):

| Tabela | Campo Merge | Tipo |
|--------|------------|------|
| Stripe_Events | event_id | Webhook ID do Stripe (100% único) |
| Charges | charge_id | ID da cobrança |
| Payment_Intents | payment_intent_id | ID do payment intent |
| Checkout_Sessions | session_id | ID da sessão |
| Customers | email ou customer_id | Email (melhor) ou ID do cliente |

### Garantias:

-  event_id é **SEMPRE único** (cada webhook tem um)
-  charge_id é **SEMPRE único** (cada cobrança tem um)
-  Email de cliente é **praticamente único** (pode ter variações)

---

## 4. O que Esta Automation Faz (Legacy)

### Processa Automaticamente:

1. **Stripe_Events** 
   - Log de TODOS os webhooks recebidos
   - Audit completo (quem, quando, o quê)
   - Payload completo guardado como JSON

2. **Charges** 
   - Cada pagamento processado
   - Montante, moeda, cliente, descrição
   - URL do recibo (para scraping posterior)

3. **Payment_Intents** 
   - Intentions de pagamento
   - Status, montante, charge vinculada

4. **Checkout_Sessions** 
   - Sessões de checkout completadas
   - Dados do cliente, montante total

5. **Customers** 
   - Clientes criados/atualizados
   - Nome, email, telefone, endereço
   - Upsert (cria se novo, atualiza se existe)

### Tempos de Processamento:

- Webhook recebido  Script executado: **~1-2 segundos**
- Dados aparece em Airtable: **Imediato**

---

## 5. O que Python Scripts Fazem (Legacy)

### PDF Generation

**Localização**: Python stripe_airtable_sync.py

- Triggered quando: Webhook recebe charge.succeeded
- Faz: Gera PDF com QR code do bilhete
- Resultado: Guarda em Cloudinary, URL em campo pdf_url

### Receipt Scraping

**Localização**: Python stripe_receipt_scraper.py

- Triggered quando: Charge sincronizada com receipt_url
- Faz: Parse HTML do recibo Stripe
- Extrai: Produtos, quantidades, mensagens personalizadas
- Resultado: Guarda em tabela Receipts

### Quando Executar:

**Opção 1: Automático** (recomendado)
- Python script executado sempre que charge.succeeded

**Opção 2: Manual**
- Botão no Streamlit para regenerar PDFs
## 6. Arquitetura Híbrida (Legacy)
egenerate_pdfs.py para dados antigos

---

## 6. Arquitetura Híbrida

### Fluxo Completo:

`

 Stripe Webhook Recebido (charge.succeeded)           

                     
                     

 Airtable Automation (Este Ficheiro)                  
  Verifica event_id (não duplica)                   
  Cria/Atualiza Charges, Customers, Sessions       
  1-2 segundos                                      

                     
        
                                 
                                 
            
    Python (1)            Python (2)       
    PDF Gen               Receipt Scraper  
     QR Code             Produtos      
     Cloudinary           Mensagens    
    ~10-15 seg            ~5-8 seg         
            
                                 
                                 
   pdf_url                  Tabela Receipts
   (Tickets table)


RESUMO:
- Airtable Automation: TEMPO REAL (dados brutos)
- Python: Processamento secundário (PDF + scraping)
`

---

## 7. Logs e Troubleshooting

### Ver Logs da Automation

1. No Airtable, ir a **Automations**
2. Clicar automation
3. Clicar **"History"**
4. Ver execuções recentes

### Padrões de Log

`
[START] Processing webhook: charge.succeeded | Event ID: evt_xxx
[SUCCESS] Event logged: evt_xxx
[SUCCESS] Charge created: ch_yyy
[SUCCESS] Customer created: email@example.com
[SKIP] Event already logged: evt_xxx
[ERROR] Creating charge: timeout
[DONE] Webhook processed: charge.succeeded
`

### Problemas Comuns

####  "Webhook endpoint failed"

**Causa**: Script tem erro ou timeout

**Solução**:
1. Ir a Stripe Webhook > Ver detalhes
2. Ver erro exato
3. Verificar script Airtable por syntax errors

####  "Records not appearing in Airtable"

**Causa**: Webhook não chegou ou tabelas têm nomes errados

**Solução**:
1. Confirmar nomes exatos: "Charges", "Customers", etc
2. Ir a Stripe > Webhooks > Ativar test mode
3. Enviar webhook teste

####  "Duplicate records criados"

**Causa**: event_id não guardado ou novo webhook enviado

**Solução**:
- Não é culpa da automation (cada event_id é único)
- Pode ser Stripe reenviando webhook

---

## 8. FAQ

### P: E se o Streamlit app cair?
**R**: A automation continua funcionando! Airtable recebe webhooks independentemente do Streamlit.

### P: E se quero testar?
**R**: 
1. Ir Stripe Dashboard > Webhooks
2. Clicar endpoint
3. Clicar "Send test webhook"
4. Ver aparecer em Airtable em ~2 segundos

### P: Posso editar o script?
**R**: Sim, mas com cuidado:
- Não mude nomes de tabelas
- Não remova indRecord() (garante anti-duplicação)
- Adicione logs com console.log()

### P: Qual é a latência?
**R**: ~1-2 segundos entre webhook Stripe  dados em Airtable

### P: E os PDFs?
**R**: Gerados separadamente pelo Python, não por esta automation

### P: Preciso de Python running o tempo todo?
**R**: Não! Só quando quer gerar PDFs ou scraping. 

Opções:
1. **On-demand**: Botão no Streamlit
2. **Scheduled**: Python script em cron job
3. **Webhook**: FastAPI ouvindo eventos do Airtable

---

## Ficheiros Relacionados

- irtable_automation_webhook.js - Este script
- stripe_airtable_sync.py - Python sync (PDFs)
- stripe_receipt_scraper.py - Python scraper (receipts)
- irtable_schema.json - Definição de todas as tabelas

---

## Próximos Passos

 Copiar código irtable_automation_webhook.js
 Colar em Airtable Automation
 Configurar webhook no Stripe
 Testar com "Send test webhook"
 Verificar dados aparecem em Airtable
 Confirmar sem duplicações

---

**Criado**: 2026-02-01
**Status**:  Pronto para usar
