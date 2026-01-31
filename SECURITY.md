# Política de Segurança

## 🔒 Versões Suportadas

| Versão | Suportada          |
| ------ | ------------------ |
| 1.0.x  | :white_check_mark: |
| < 1.0  | :x:                |

## 🚨 Reportar Vulnerabilidades

Se você descobrir uma vulnerabilidade de segurança, **NÃO** abra uma issue pública.

Por favor, envie um email para: [seu-email-seguranca@exemplo.com]

Inclua:
- Descrição detalhada da vulnerabilidade
- Passos para reproduzir
- Impacto potencial
- Sugestões de correção (se houver)

Responderemos em até 48 horas.

## ✅ Boas Práticas de Segurança

### Variáveis de Ambiente
**NUNCA** commite o arquivo `.env`:
```env
# ❌ NUNCA FAÇA ISSO
STRIPE_API_KEY=sk_live_xxxxx  # Exposto no GitHub!

# ✅ SEMPRE use .env e adicione ao .gitignore
```

### Chaves de API
- Use **Personal Access Tokens** do Airtable com permissões mínimas
- Rotacione chaves regularmente
- Use **modo test** do Stripe em desenvolvimento
- Nunca logue chaves completas

### Validação de BASE_ID
O sistema implementa validação rigorosa:
```python
EXPECTED_BASE_ID = "apppvZnFTV6a33RUf"

# Falha se tentar usar outra base
if base_id != EXPECTED_BASE_ID:
    raise ValueError("BASE_ID INCORRETO!")
```

### Dados Sensíveis
- Não armazene dados de cartão (use Stripe Elements)
- Não logue informações pessoais completas
- Use HTTPS em produção
- Valide todos os inputs de usuários

## 🛡️ Checklist de Deploy

Antes de fazer deploy em produção:

- [ ] `.env` não está no repositório
- [ ] Chaves de produção configuradas corretamente
- [ ] HTTPS habilitado
- [ ] Webhooks do Stripe com assinatura verificada
- [ ] Logs não expõem dados sensíveis
- [ ] BASE_ID validado e correto
- [ ] Backups configurados
- [ ] Rate limiting implementado

## 📋 Conformidade

Este projeto processa dados de pagamento através do Stripe, que é certificado PCI DSS Level 1.

**Responsabilidades:**
- Stripe: Processamento seguro de pagamentos
- Airtable: Armazenamento de dados de eventos
- Este projeto: Sincronização e gestão de dados

**Não armazenamos:**
- Números de cartão
- CVV
- Dados bancários sensíveis

## 🔄 Atualizações de Segurança

Mantenha as dependências atualizadas:
```bash
pip install --upgrade stripe requests python-dotenv
```

Monitore vulnerabilidades:
```bash
pip-audit
```

## 📞 Contato

Para questões de segurança: [seu-email-seguranca@exemplo.com]

---

**Última atualização:** 31 de Janeiro de 2026
