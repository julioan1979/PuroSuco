from datetime import datetime, timezone
from airtable_client import upsert_record, list_tables, get_airtable_config
from app_logger import log_ticket_validation
import base64
import requests


def validate_qrcode(qrcode_data: str, validated_by: str = None) -> dict:
    """
    Validate a QR code by searching for matching ticket.
    Returns: {"success": bool, "ticket_id": str, "ticket_data": dict, "error": str}
    """
    try:
        # Parse QR code data format: "TICKET:ticket_id:customer_email"
        if not qrcode_data or not qrcode_data.startswith("TICKET:"):
            log_ticket_validation("unknown", qrcode_data or "", validated_by, "warning", "Formato inválido")
            return {"success": False, "error": "QR code format inválido"}

        parts = qrcode_data.split(":")
        if len(parts) < 2:
            log_ticket_validation("unknown", qrcode_data, validated_by, "warning", "Formato incompleto")
            return {"success": False, "error": "QR code format inválido"}

        ticket_id = parts[1]
        ticket_data = get_ticket_data(ticket_id)

        if not ticket_data.get("success"):
            log_ticket_validation(ticket_id, qrcode_data, validated_by, "error", ticket_data.get("error"))
            return {"success": False, "error": ticket_data.get("error", "Bilhete não encontrado")}

        status = (ticket_data.get("status") or "").lower()
        if status == "validated":
            log_ticket_validation(ticket_id, qrcode_data, validated_by, "warning", "Bilhete já validado")
            return {
                "success": False,
                "error": "Bilhete já validado",
                "already_validated": True,
                "ticket_id": ticket_id,
                "ticket_data": ticket_data
            }

        log_ticket_validation(ticket_id, qrcode_data, validated_by, "success")
        return {
            "success": True,
            "ticket_id": ticket_id,
            "qrcode_data": qrcode_data,
            "validated_at": datetime.now(tz=timezone.utc).isoformat(),
            "validated_by": validated_by,
            "ticket_data": ticket_data
        }

    except Exception as exc:
        log_ticket_validation("unknown", qrcode_data or "", validated_by, "error", str(exc))
        return {"success": False, "error": str(exc)}


def mark_ticket_as_validated(ticket_id: str, validated_by: str = None) -> bool:
    """
    Mark a ticket as validated in Airtable.
    """
    try:
        fields = {
            "ticket_id": ticket_id,
            "validated_at": datetime.now(tz=timezone.utc).isoformat(),
            "validated_by": validated_by or "system",
            "status": "validated"
        }
        upsert_record("Tickets", fields, merge_on="ticket_id")
        log_ticket_validation(ticket_id, "", validated_by, "success")
        return True
    except Exception as exc:
        log_ticket_validation(ticket_id, "", validated_by, "error", str(exc))
        return False


def get_ticket_data(ticket_id: str) -> dict:
    """
    Retrieve ticket data from Airtable Tickets table.
    Searches by ticket_id field.
    """
    try:
        api_key, base_id = get_airtable_config()
        # Search for ticket by ID using filterByFormula
        formula = f"{{ticket_id}}='{ticket_id}'"
        url = f"https://api.airtable.com/v0/{base_id}/Tickets"
        params = {
            "filterByFormula": formula,
            "maxRecords": 1
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        records = resp.json().get("records", [])
        
        if records:
            record = records[0]
            fields = record.get("fields", {})
            return {
                "success": True,
                "ticket_id": fields.get("ticket_id"),
                "status": fields.get("status", "pending"),
                "customer_name": fields.get("customer_name"),
                "customer_email": fields.get("customer_email"),
                "validated_at": fields.get("validated_at"),
                "validated_by": fields.get("validated_by"),
                "pdf_url": fields.get("pdf_url"),
                "pdf_attachment": fields.get("pdf_attachment"),
                "airtable_id": record.get("id")
            }
        else:
            return {"success": False, "error": f"Ticket {ticket_id} não encontrado"}
    except Exception as exc:
        log_ticket_validation(ticket_id, "", None, "error", str(exc))
        return {"success": False, "error": str(exc)}


def get_ticket_by_charge_id(charge_id: str) -> dict:
    """
    Retrieve ticket data from Airtable Tickets table by charge_id.
    """
    try:
        if not charge_id:
            return {"success": False, "error": "charge_id vazio"}
        api_key, base_id = get_airtable_config()
        formula = f"{{charge_id}}='{charge_id}'"
        url = f"https://api.airtable.com/v0/{base_id}/Tickets"
        params = {
            "filterByFormula": formula,
            "maxRecords": 1
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        records = resp.json().get("records", [])

        if records:
            record = records[0]
            fields = record.get("fields", {})
            return {
                "success": True,
                "ticket_id": fields.get("ticket_id"),
                "status": fields.get("status", "pending"),
                "customer_name": fields.get("customer_name"),
                "customer_email": fields.get("customer_email"),
                "validated_at": fields.get("validated_at"),
                "validated_by": fields.get("validated_by"),
                "pdf_url": fields.get("pdf_url"),
                "pdf_attachment": fields.get("pdf_attachment"),
                "airtable_id": record.get("id"),
                "charge_id": charge_id
            }
        else:
            return {"success": False, "error": f"Ticket não encontrado para charge {charge_id}"}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def download_ticket_pdf(ticket_id: str) -> tuple:
    """
    Download ticket PDF from Airtable (base64 decoded).
    Returns: (pdf_bytes, filename) or (None, None) if not found
    """
    try:
        ticket_data = get_ticket_data(ticket_id)
        if not ticket_data.get("success"):
            return None, None
        
        api_key, base_id = get_airtable_config()
        record_id = ticket_data.get("airtable_id")
        
        # Fetch full record to get PDF attachment
        url = f"https://api.airtable.com/v0/{base_id}/Tickets/{record_id}"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        record = resp.json()
        
        # Check for PDF attachment
        pdf_field = record["fields"].get("pdf_attachment", [])
        if not pdf_field or not isinstance(pdf_field, list) or len(pdf_field) == 0:
            return None, None
        
        pdf_url = pdf_field[0].get("url")
        filename = pdf_field[0].get("filename", f"ticket_{ticket_id}.pdf")
        
        if pdf_url:
            resp = requests.get(pdf_url, timeout=30)
            resp.raise_for_status()
            return resp.content, filename
        
        return None, None
    except Exception as exc:
        log_ticket_validation(ticket_id, "", None, "error", f"Download PDF: {str(exc)}")
        return None, None


def get_ticket_statistics() -> dict:
    """
    Get ticket statistics: total, validated, pending.
    Queries Airtable for aggregated data.
    """
    try:
        api_key, base_id = get_airtable_config()
        url = f"https://api.airtable.com/v0/{base_id}/Tickets"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # Get all tickets with pagination
        all_records = []
        offset = None
        params = {"pageSize": 100}
        
        while True:
            if offset:
                params["offset"] = offset
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            all_records.extend(data.get("records", []))
            offset = data.get("offset")
            if not offset:
                break
        
        # Count by status
        validated = sum(1 for r in all_records if r["fields"].get("status") == "validated")
        pending = sum(1 for r in all_records if r["fields"].get("status") == "pending")
        
        return {
            "success": True,
            "total_tickets": len(all_records),
            "validated": validated,
            "pending": pending,
            "percentage_validated": round((validated / len(all_records) * 100) if all_records else 0, 2)
        }
    except Exception as exc:
        log_ticket_validation("stats", "", None, "error", str(exc))
        return {"success": False, "error": str(exc)}
