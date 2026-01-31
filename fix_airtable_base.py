import os
import glob
from pathlib import Path

# O BASE_ID correto do .env
CORRECT_BASE_ID = "apppvZnFTV6a33RUf"
# O BASE_ID errado que está sendo usado
WRONG_BASE_ID = "appzwzHD5YUCyIx63"

print("=" * 80)
print("DIAGNÓSTICO: Procurando BASE_ID hardcoded nos arquivos Python")
print("=" * 80)
print(f"\nBASE_ID CORRETO (do .env): {CORRECT_BASE_ID}")
print(f"BASE_ID ERRADO (encontrado nos logs): {WRONG_BASE_ID}")
print("\n" + "=" * 80)

# Verifica o que está no .env
print("\n1. Verificando arquivo .env:")
env_file = Path(".env")
if env_file.exists():
    with open(env_file, "r") as f:
        for line in f:
            if "Airtable_Base_ID" in line or "AIRTABLE_BASE_ID" in line:
                print(f"   ✓ {line.strip()}")
else:
    print("   ✗ Arquivo .env não encontrado!")

# Verifica variáveis de ambiente carregadas
print("\n2. Verificando variáveis de ambiente:")
airtable_base = os.getenv("Airtable_Base_ID") or os.getenv("AIRTABLE_BASE_ID")
if airtable_base:
    print(f"   ✓ Variável carregada: {airtable_base}")
else:
    print("   ✗ Variável de ambiente não carregada!")

# Procura por arquivos Python com o BASE_ID errado hardcoded
print(f"\n3. Procurando '{WRONG_BASE_ID}' em arquivos Python:")
found_files = []
python_files = glob.glob("**/*.py", recursive=True)

for file_path in python_files:
    # Ignora este próprio script e pastas específicas
    if "fix_airtable_base.py" in file_path or "venv" in file_path or ".venv" in file_path:
        continue
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            if WRONG_BASE_ID in content:
                found_files.append(file_path)
                print(f"\n   ❌ ENCONTRADO EM: {file_path}")
                # Mostra as linhas onde aparece
                lines = content.split("\n")
                for i, line in enumerate(lines, 1):
                    if WRONG_BASE_ID in line:
                        print(f"      Linha {i}: {line.strip()}")
    except Exception as e:
        pass

# Procura também pelo BASE_ID correto
print(f"\n4. Verificando uso do BASE_ID correto '{CORRECT_BASE_ID}':")
correct_files = []
for file_path in python_files:
    if "fix_airtable_base.py" in file_path or "venv" in file_path or ".venv" in file_path:
        continue
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            if CORRECT_BASE_ID in content:
                correct_files.append(file_path)
                print(f"\n   ✓ Encontrado em: {file_path}")
    except Exception as e:
        pass

# Resumo
print("\n" + "=" * 80)
print("RESUMO DO DIAGNÓSTICO:")
print("=" * 80)
if found_files:
    print(f"\n⚠️  BASE_ID ERRADO encontrado em {len(found_files)} arquivo(s):")
    for f in found_files:
        print(f"   - {f}")
    print("\n✅ AÇÃO NECESSÁRIA: Substituir os BASE_IDs hardcoded por:")
    print("   os.getenv('Airtable_Base_ID') ou os.getenv('AIRTABLE_BASE_ID')")
else:
    print("\n✓ Nenhum BASE_ID errado hardcoded encontrado nos arquivos Python.")
    print("  O problema pode ser:")
    print("  - Cache de imports do Python")
    print("  - Múltiplos arquivos .env")
    print("  - Variável de ambiente do sistema")

if correct_files:
    print(f"\nℹ️  BASE_ID CORRETO encontrado hardcoded em {len(correct_files)} arquivo(s)")

print("\n" + "=" * 80)
