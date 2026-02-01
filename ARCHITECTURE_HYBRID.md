#  Arquitetura Híbrida: Airtable + Python

## Resposta às Tuas Perguntas

### 1 "Os dois de hora a hora?" (Funcionam bem juntos?)

**Resposta: SIM, PERFEITAMENTE! **

- **stripe-webhook-airtable (Railway)**  Recebe webhooks em TEMPO REAL (~1-2 seg)
- **Python Scripts**  Processam dados em paralelo (~10-15 seg)
- **Resultado**: Dados aparecem imediatamente, processamento secundário em background

### 2 "Script do aplicativo só deve atualizar dados que não tenha na base?"

**Resposta: SIM, EXATAMENTE! **

`python
# Python Script - Apenas processa dados NOVOS

# ANTES de gerar PDF, verifica:
if existing_ticket_has_pdf_url:
    print("PDF já gerado, skipping...")
else:
    print("PDF não existe, gerando...")
    generate_pdf()
    upload_to_cloudinary()

# ANTES de scraping, verifica:
if existing_receipt_in_table:
    print("Recibo já foi scrapeado...")
else:
    print("Recibo novo, scrapiando...")
    scrape_receipt()
    upsert_to_airtable()
`

Isto evita:
-  Reprocessamento de dados
-  Uso excessivo de API Cloudinary
-  Carregamento desnecessário no Stripe

---

## Fluxo Completo (Passo a Passo)

### Cenário: Cliente faz pagamento

`

 PASSO 1: Cliente paga no Stripe                             
 (ex: Niver Bia 2026 - €15.00)                              

             
             

 PASSO 2: Stripe envia webhook "charge.succeeded"            
 Tempo: IMEDIATO                                             

             
             

 PASSO 3: stripe-webhook-airtable (Railway)                 
  Endpoint: https://stripe-webhook-airtable-production.up.railway.app/stripe/webhook
  Repo: https://github.com/julioan1979/stripe-webhook-airtable
                                                              
  performUpsert por event_id / charge_id (não duplica)     
  Cria/Atualiza: Charges table                             
  Cria/Atualiza: Customers table                           
  Log em Stripe_Events table                               
  Guarda receipt_url                                       
                                                              
 Tempo: ~1-2 segundos                                        
 Resultado: Dados aparecem imediatamente em Airtable         

             
             

 PASSO 4: Python Script (stripe_airtable_sync.py)            
 Triggered: Quando detecta charge SEM pdf_url                
                                                              
  Verifica se charge já tem ticket + PDF                   
  Gera PDF com QR code                                     
  Upload para Cloudinary                                   
  Guarda URL em pdf_url field                              
                                                              
 Tempo: ~10-15 segundos                                      
 Resultado: Bilhete com PDF pronto                           

             
             

 PASSO 5: Python Script (stripe_receipt_scraper.py)          
 Triggered: Quando detecta charge COM receipt_url            
                                                              
  Verifica se recibo já foi scrapeado                      
  Faz fetch do HTML do recibo                              
  Extrai: produtos, quantidades, mensagens                 
  Guarda em Receipts table                                 
                                                              
 Tempo: ~5-8 segundos                                        
 Resultado: Dados de recibo disponível para análise          

             
             
        
          COMPLETO        
         - Charge: Criada   
         - Cliente: Criado  
         - Bilhete: Gerado  
         - Recibo: Scrapeado
         - PDF: Pronto      
        
`

---

## Benefícios desta Arquitetura

### 1. Sem Carregamento Pesado no Início

 **ANTES** (Python puro):
- Streamlit inicia  Carrega TODOS os charges do Stripe (~5-10 seg)
- Verifica CADA um por PDF, recibo, etc. (~30-60 seg)
- UI congelada enquanto carrega

 **DEPOIS** (Airtable + Python):
- Streamlit inicia  Apenas busca dados já em Airtable (~1-2 seg)
- UI responsiva IMEDIATAMENTE
- Dados em background, sem bloquear

### 2. Zero Duplicações

**stripe-webhook-airtable (Railway)**:
- `performUpsert` por **event_id** e **charge_id** (Stripe garante unicidade)
- Mesmo se webhook for reenviado  Sem duplicação

**Python Scripts**:
- Verificam `merge_on="charge_id"` antes de upsert
- Verificam se `pdf_url` já existe
- Verificam se `receipt` já foi scrapeado
  
**Resultado**: os scripts complementam dados faltantes sem criar duplicados.
### Webhook Oficial (Produção)

| Recurso | Propósito |
|---------|-----------|
| https://stripe-webhook-airtable-production.up.railway.app/stripe/webhook | Endpoint oficial que recebe eventos da Stripe |
| https://github.com/julioan1979/stripe-webhook-airtable | Repositório responsável pelo serviço |

| AIRTABLE_AUTOMATION_GUIDE.md | **Guia de setup** - Fluxo oficial (Railway) + histórico da automation |
###  Webhook Oficial (Railway)

- [ ] Endpoint oficial configurado no Stripe
- [ ] URL em produção: https://stripe-webhook-airtable-production.up.railway.app/stripe/webhook
- [ ] Repositório de referência: https://github.com/julioan1979/stripe-webhook-airtable

- [ ] Colar webhook URL oficial (Railway)
- [ ] Verificar logs no serviço Railway

###  Histórico / Deprecated

- [ ] **Legacy**: Airtable Automation com `airtable_automation_webhook.js`
- [ ] Evitar habilitar para não gerar dupla ingestão
- Logs com timestamp, status, erros

---

## Ficheiros do Projeto

### Airtable (Este Repositório)

| Ficheiro | Propósito |
|----------|-----------|
| irtable_automation_webhook.js | **Script JavaScript executado em Airtable** - Processa webhooks em tempo real |
| AIRTABLE_AUTOMATION_GUIDE.md | **Guia de setup** - Como configurar no Airtable e Stripe |
| ARCHITECTURE_HYBRID.md | **Este ficheiro** - Explicação da arquitetura |

### Python Scripts

| Ficheiro | Propósito | Trigger |
|----------|-----------|---------|
| stripe_airtable_sync.py | Sincroniza charges, gera bilhetes | Webhook ou manual |
| stripe_receipt_scraper.py | Extrai dados de recibos Stripe | Após charge sync |
| pdf_generator.py | Gera PDF com QR code | Chamado por sync |

### Schema

| Ficheiro | Propósito |
|----------|-----------|
| irtable_schema.json | Definição de todas as 10 tabelas + 100+ campos |
| pply_airtable_schema.py | Aplica schema ao Airtable base |

---

## Setup Checklist

###  Airtable Automation

- [ ] Ficheiro irtable_automation_webhook.js existe
- [ ] Documentação AIRTABLE_AUTOMATION_GUIDE.md lida
- [ ] Automation criada no Airtable
- [ ] Código JavaScript colado em "Run script" action
- [ ] Webhook URL copiada

###  Stripe Webhooks

- [ ] Ir https://dashboard.stripe.com/webhooks
- [ ] Criar novo endpoint
- [ ] Colar webhook URL do Airtable
- [ ] Selecionar eventos:
  - charge.succeeded
  - payment_intent.succeeded
  - checkout.session.completed
  - customer.created/updated
- [ ] Testar com "Send test webhook"

###  Python Setup (já completo)

- [ ] stripe_airtable_sync.py com import de scraper
- [ ] stripe_receipt_scraper.py criado
- [ ] equirements.txt atualizado com BeautifulSoup4
- [ ] Dependências instaladas (pip install -r requirements.txt)
- [ ] Testes passando

###  Validação

- [ ] Enviar webhook teste no Stripe
- [ ] Verificar dados em Airtable (~2 seg)
- [ ] Confirmar sem duplicações
- [ ] Verificar logs na Airtable Automation

---

## Performance Esperada

### Latência de Ponta a Ponta

`
Cliente paga (T+0s)
         
Stripe envia webhook (T+0.1s)
         
Airtable recebe (T+0.5s)
         
JavaScript executa, cria records (T+1.5s)  Dados disponíveis!
         
Python detecta e inicia PDF gen (T+2s)
         
PDF gerado e uploaded (T+12s)  Bilhete pronto!
         
Python inicia receipt scraping (T+13s)
         
Recibo scrapeado e guardado (T+18s)  Análise pronta!
`

### Total: ~20 segundos do pagamento até completo

-  Dados: 1-2 segundos
-  PDF: 10-15 segundos
-  Recibo: 5-8 segundos

---

## Próximas Melhorias (Opcional)

### 1. Notificações em Tempo Real

- Enviar email quando PDF pronto
- Webhook para aplicação externa

### 2. Rate Limiting

- Limitar geração de PDFs em picos
- Queue com fila de espera

### 3. Retry Logic

- Se scraping falhar, retry depois
- Exponential backoff

### 4. Analytics

- Dashboard no Airtable
- Métricas de performance

---

**Criado**: 2026-02-01
**Status**:  Implementação Completa
**Autores**: Julio (PuroSuco)
