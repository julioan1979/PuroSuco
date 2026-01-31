import os
import requests
from dotenv import load_dotenv

load_dotenv()

# ⚠️ BLINDAGEM DE SEGURANÇA: BASE_ID esperado do projeto PuroSuco
# Este é o ÚNICO BASE_ID válido. Qualquer outro é ERRO!
EXPECTED_BASE_ID = "apppvZnFTV6a33RUf"


def _get_env(*names):
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


def get_airtable_config():
    api_key = _get_env("AIRTABLE_API_KEY", "Airtable_API_Key", "Airtble_API_Key")
    
    # 🔒 SEGURANÇA TOTAL: Usa SEMPRE o BASE_ID hardcoded do projeto
    # Ignora qualquer variável de ambiente para evitar erros
    base_id = EXPECTED_BASE_ID
    
    # ⚠️ VALIDAÇÃO CRÍTICA: Verifica se a API key existe
    if not api_key:
        raise ValueError(
            "❌ ERRO CRÍTICO: AIRTABLE_API_KEY deve estar no arquivo .env\n"
            "Verifique se o arquivo .env contém:\n"
            "  - AIRTABLE_API_KEY=sua_chave\n"
            f"  BASE_ID será sempre: {EXPECTED_BASE_ID}"
        )
    
    return api_key, base_id


def _headers(api_key):
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }


def _table_url(base_id, table, record_id=None):
    if record_id:
        return f"https://api.airtable.com/v0/{base_id}/{table}/{record_id}"
    return f"https://api.airtable.com/v0/{base_id}/{table}"


def _escape_formula_value(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE()" if value else "FALSE()"
    if isinstance(value, (int, float)):
        return str(value)
    return str(value).replace("'", "\\'")


def _find_record_id(table, field_name, value):
    api_key, base_id = get_airtable_config()
    if value is None:
        return None
    escaped = _escape_formula_value(value)
    formula = f"{{{field_name}}}='{escaped}'" if not isinstance(value, bool) else f"{{{field_name}}}={escaped}"
    params = {"filterByFormula": formula, "maxRecords": 1}
    resp = requests.get(_table_url(base_id, table), headers=_headers(api_key), params=params, timeout=30)
    resp.raise_for_status()
    records = resp.json().get("records", [])
    return records[0]["id"] if records else None


def update_record(table, record_id, fields):
    api_key, base_id = get_airtable_config()
    resp = requests.patch(_table_url(base_id, table, record_id), headers=_headers(api_key), json={"fields": fields}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def upsert_record(table, fields, merge_on=None):
    api_key, base_id = get_airtable_config()
    url = _table_url(base_id, table)
    payload = {"records": [{"fields": fields}]}
    if merge_on:
        payload["performUpsert"] = {"fieldsToMergeOn": [merge_on]}
    resp = requests.post(url, headers=_headers(api_key), json=payload, timeout=30)
    if resp.status_code != 422 or not merge_on:
        resp.raise_for_status()
        return resp.json()

    # Fallback: manual upsert (find + update/create)
    record_id = _find_record_id(table, merge_on, fields.get(merge_on))
    if record_id:
        return update_record(table, record_id, fields)
    return create_record(table, fields)


def create_record(table, fields):
    return upsert_record(table, fields, merge_on=None)


def list_tables():
    api_key, base_id = get_airtable_config()
    url = f"https://api.airtable.com/v0/meta/bases/{base_id}/tables"
    resp = requests.get(url, headers=_headers(api_key), timeout=30)
    resp.raise_for_status()
    return resp.json()


def create_table(table_payload):
    api_key, base_id = get_airtable_config()
    url = f"https://api.airtable.com/v0/meta/bases/{base_id}/tables"
    resp = requests.post(url, headers=_headers(api_key), json=table_payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def list_fields(table_id):
    api_key, base_id = get_airtable_config()
    url = f"https://api.airtable.com/v0/meta/bases/{base_id}/tables/{table_id}/fields"
    resp = requests.get(url, headers=_headers(api_key), timeout=30)
    resp.raise_for_status()
    return resp.json()


def create_field(table_id, field_payload):
    api_key, base_id = get_airtable_config()
    url = f"https://api.airtable.com/v0/meta/bases/{base_id}/tables/{table_id}/fields"
    resp = requests.post(url, headers=_headers(api_key), json=field_payload, timeout=30)
    resp.raise_for_status()
    return resp.json()
