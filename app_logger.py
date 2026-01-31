import os
import uuid
from datetime import datetime, timezone
from airtable_client import upsert_record

LOG_LEVEL_INFO = "INFO"
LOG_LEVEL_WARNING = "WARNING"
LOG_LEVEL_ERROR = "ERROR"
LOG_LEVEL_DEBUG = "DEBUG"


def _ts_now_iso():
    return datetime.now(tz=timezone.utc).isoformat()


def log_action(
    module: str,
    action: str,
    status: str = "success",
    message: str = None,
    level: str = LOG_LEVEL_INFO,
    user_id: str = None,
    object_type: str = None,
    object_id: str = None,
    error_details: str = None,
):
    """Log an action to Airtable Logs table and optionally to console."""
    log_id = str(uuid.uuid4())
    
    fields = {
        "log_id": log_id,
        "timestamp": _ts_now_iso(),
        "level": level,
        "module": module,
        "action": action,
        "status": status,
        "message": message or "",
        "user_id": user_id,
        "object_type": object_type,
        "object_id": object_id,
        "error_details": error_details or ""
    }
    
    console_msg = f"[{level}] {module}.{action} ({status}): {message or object_id}"
    print(console_msg)
    
    try:
        upsert_record("Logs", fields, merge_on="log_id")
    except Exception as e:
        print(f"[ERROR] Falha ao registar log em Airtable: {str(e)}")
    
    return log_id


def log_sync(object_type: str, object_id: str, status: str, message: str = None):
    """Log a Stripe→Airtable sync action."""
    log_action(
        module="sync",
        action=f"sync_{object_type}",
        status=status,
        message=message,
        level=LOG_LEVEL_INFO if status == "success" else LOG_LEVEL_ERROR,
        object_type=object_type,
        object_id=object_id
    )


def log_pdf_generation(ticket_id: str, status: str, file_size: int = None, error: str = None):
    """Log PDF generation."""
    log_action(
        module="pdf",
        action="generate_ticket_pdf",
        status=status,
        message=f"PDF size: {file_size} bytes" if file_size else None,
        level=LOG_LEVEL_INFO if status == "success" else LOG_LEVEL_ERROR,
        object_type="ticket",
        object_id=ticket_id,
        error_details=error
    )


def log_ticket_validation(ticket_id: str, qrcode_data: str, validated_by: str = None, status: str = "success", error: str = None):
    """Log ticket validation/picking."""
    log_action(
        module="picking",
        action="validate_ticket",
        status=status,
        message=f"QR code: {qrcode_data[:20]}..." if qrcode_data else None,
        level=LOG_LEVEL_INFO if status == "success" else LOG_LEVEL_WARNING,
        user_id=validated_by,
        object_type="ticket",
        object_id=ticket_id,
        error_details=error
    )
