# 🔄 Sincronização Direta com Airtable (Dashboard)

## Novidade: Sincronização Independente do Webhook

Agora você pode sincronizar e gerar bilhetes **diretamente do app Streamlit**, sem depender do webhook do Stripe!

---

## 📍 Onde Encontrar

### 1. **Dashboard** (Menu principal)
- **Botão: 🔄 Sincronizar Agora**
  - Sincroniza últimos 50 charges com Airtable
  - Gera bilhetes para charges sem ticket
  - ⏱️ Rápido (~5-10 segundos)

- **Botão: 📄 Sincronizar + Gerar PDFs**
  - Sincroniza dados + Gera e envia PDFs como attachments
  - Barra de progresso visual
  - ⏱️ Mais lento (~30-60 segundos)

### 2. **Airtable** (Menu avançado)
- **Botão: Enviar Charges para Airtable**
  - Sincroniza apenas dados de charge
  - Sem gerar bilhetes

- **Botão: Enviar Charges + Gerar Bilhetes PDF** ⭐ NOVO
  - Sincroniza dados E gera bilhetes com PDFs
  - Com barra de progresso e status em tempo real
  - Mensagens de erro detalhadas por charge

---

## 🎯 Casos de Uso

### Caso 1: Sincronização Rápida (sem PDFs)
```
Dashboard → 🔄 Sincronizar Agora
↓
✅ Charges no Airtable em segundos
✅ Bilhetes criados (sem PDF ainda)
```

### Caso 2: Sincronização Completa (com PDFs)
```
Dashboard → 📄 Sincronizar + Gerar PDFs
  ou
Airtable → Enviar Charges + Gerar Bilhetes PDF
↓
✅ Charges no Airtable
✅ Bilhetes criados
✅ PDFs enviados como attachments
✅ Pronto para download/visualização
```

### Caso 3: Gerar Bilhete Individual
```
Bilhetes → Selecionar Charge → Gerar Bilhete
↓
✅ Um bilhete com PDF
```

### Caso 4: Gerar Bilhetes em Lote
```
Bilhetes → Definir quantidade → Gerar Bilhetes em Lote
↓
✅ Múltiplos bilhetes com PDFs
```

---

## 🔍 O que Acontece Internamente

### Durante Sincronização Completa:

1. **Por cada Charge:**
   - ✅ Envia dados do charge para `Charges` table
   - ✅ Envia dados do cliente para `Customers` table
   - ✅ Gera PDF do bilhete (~5MB)
   - ✅ Cria registro em `Tickets` table
   - ✅ Faz upload do PDF para campo `pdf_attachment`
   - ✅ Cria QR code em `QRCodes` table

2. **Logs:**
   - `[INFO]` - Ticket criado
   - `[SUCCESS]` - PDF enviado
   - `[WARNING]` - Problemas menores (não interrompe)
   - `[ERROR]` - Erros graves

3. **Resultado:**
   - ✅ Charge sincronizado
   - ✅ Bilhete criado com QR code
   - ✅ PDF acessível no Airtable

---

## 📊 Status em Tempo Real

Quando você clica em **"Enviar Charges + Gerar Bilhetes PDF"**:

```
🔄 Processados: 1 | Sincronizados: 1 | Bilhetes: 1
🔄 Processados: 2 | Sincronizados: 2 | Bilhetes: 2
🔄 Processados: 3 | Sincronizados: 3 | Bilhetes: 2  ⚠️ (PDF grande?)
...
✅ Charges sincronizadas: 50 | Bilhetes gerados: 48 | Erros: 2
```

---

## ⚙️ Configurações

### Limite de Registros (Default: 200)
```
Airtable → Máx. registros para sincronizar: 200
```

Altere para processar mais (até 2000):
- ⚡ Mais rápido: 50-100 (recomendado)
- 🐢 Mais completo: 500-2000 (lento)

---

## 🚀 Workflow Recomendado

### Durante o Evento:
1. Clientes fazem pagamentos
2. Dashboard monitora em tempo real
3. Se necessário, clique **🔄 Sincronizar Agora** manualmente
4. Bilhetes aparecem no Airtable
5. Clientes recebem PDFs

### Após o Evento:
1. Vá para **Airtable** menu
2. Clique **Enviar Charges + Gerar Bilhetes PDF**
3. Processe todos os charges de uma vez
4. Todos os bilhetes em uma só ação

### Recuperação (se webhook falhou):
1. Dashboard → **📄 Sincronizar + Gerar PDFs**
2. Processa últimos 50 charges
3. Gera bilhetes faltantes
4. Tudo sincronizado

---

## 📱 Validação de Bilhetes

Após sincronizar:
1. Vá para menu **Picking**
2. Leia QR codes com câmera
3. Bilhetes aparecem como validados em tempo real
4. Sincronizado com Airtable automaticamente

---

## 📋 Resumo de Funcionalidades

| Funcionalidade | Webhook | Dashboard | Airtable Menu |
|---|---|---|---|
| Sincronizar dados | ✅ | ✅ | ✅ |
| Gerar bilhetes | ✅ | ✅ | ✅ |
| Com PDFs | ✅ | ✅ (novo) | ✅ (novo) |
| Progresso visual | ❌ | ✅ (novo) | ✅ (novo) |
| Manual vs Auto | Auto | Manual | Manual |
| Velocidade | Rápido | Rápido | Rápido |

---

## 🛠️ Troubleshooting

### PDFs não aparecem no Airtable?
1. Verifique os logs do terminal (procure por `[ERROR]`)
2. Confirme que a coluna `pdf_attachment` existe
3. Tente sincronizar novamente

### Sincronização lenta?
1. Reduza "Máx. registros" para 50-100
2. Feche outras abas do navegador
3. Verifique conexão internet

### Alguns bilhetes falharam?
1. Veja o erro na mensagem final
2. Tente sincronizar só aquele charge individual
3. Verifique tamanho do PDF (se > 5MB, falha)

---

**Última atualização:** 31/01/2026  
**Status:** ✅ Funcional - Pronto para Produção
