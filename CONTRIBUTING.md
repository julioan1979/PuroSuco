# Guia de Contribuição

Obrigado por considerar contribuir para o PuroSuco! 🎉

## Como Contribuir

### Reportar Bugs

Encontrou um bug? Abra uma issue com:
- Descrição clara do problema
- Passos para reproduzir
- Comportamento esperado vs. observado
- Screenshots (se aplicável)
- Versão do Python e dependências

### Sugerir Melhorias

Tem uma ideia? Abra uma issue descrevendo:
- O problema que resolve
- Solução proposta
- Alternativas consideradas
- Impacto esperado

### Pull Requests

1. **Fork** o repositório
2. **Clone** seu fork localmente
3. **Crie uma branch** descritiva:
   ```bash
   git checkout -b feature/minha-feature
   # ou
   git checkout -b fix/corrige-bug
   ```

4. **Desenvolva** sua feature/correção
   - Siga o estilo de código do projeto
   - Adicione testes se aplicável
   - Atualize a documentação

5. **Teste** suas mudanças:
   ```bash
   # Execute os testes
   pytest
   
   # Verifique formatação
   black .
   flake8
   ```

6. **Commit** com mensagens claras:
   ```bash
   git commit -m "feat: adiciona funcionalidade X"
   git commit -m "fix: corrige erro Y"
   git commit -m "docs: atualiza README"
   ```

7. **Push** para seu fork:
   ```bash
   git push origin feature/minha-feature
   ```

8. **Abra um Pull Request** na branch `main`

## Padrões de Código

### Python
- Use **Python 3.13+**
- Siga **PEP 8**
- Use **type hints** quando possível
- Docstrings em **português** ou **inglês**

### Commits
Siga o padrão de Conventional Commits:
- `feat:` Nova funcionalidade
- `fix:` Correção de bug
- `docs:` Apenas documentação
- `style:` Formatação (sem mudança de código)
- `refactor:` Refatoração de código
- `test:` Adiciona/corrige testes
- `chore:` Manutenção/tarefas

### Documentação
- Atualize o README.md se necessário
- Adicione comentários em código complexo
- Documente funções públicas

## Estrutura de Testes

```python
# tests/test_airtable_client.py
import pytest
from airtable_client import get_airtable_config

def test_get_airtable_config_valida_base_id():
    """Testa validação rigorosa do BASE_ID"""
    # Implementação do teste
    pass
```

## Revisão de Código

Todos os PRs serão revisados considerando:
- ✅ Funcionalidade implementada corretamente
- ✅ Testes passando
- ✅ Código limpo e legível
- ✅ Documentação atualizada
- ✅ Sem breaking changes (ou bem documentados)

## Dúvidas?

Abra uma issue com a tag `question` ou entre em contato!

Obrigado pela contribuição! 🙌
