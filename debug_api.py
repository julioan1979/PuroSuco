import os
import requests
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("AIRTABLE_API_KEY") or os.getenv("Airtable_API_Key")
base_id = "apppvZnFTV6a33RUf"

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

# Get Tickets table ID
tables_url = f"https://api.airtable.com/v0/meta/bases/{base_id}/tables"
resp = requests.get(tables_url, headers=headers, timeout=30)
tables = resp.json()["tables"]

tickets_table_id = None
for table in tables:
    if table["name"] == "Tickets":
        tickets_table_id = table["id"]
        break

print(f"Tickets table ID: {tickets_table_id}")

# Try to get fields
fields_url = f"https://api.airtable.com/v0/meta/bases/{base_id}/tables/{tickets_table_id}/fields"
resp = requests.get(fields_url, headers=headers, timeout=30)
print(f"Status: {resp.status_code}")
print(f"Response: {resp.json()}")
