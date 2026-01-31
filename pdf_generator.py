import uuid
import qrcode
from io import BytesIO
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import base64
from app_logger import log_pdf_generation

BACKGROUND_PATH = "pdf_background/background_V1_PuroSuco.png"


def generate_qrcode_data(ticket_id: str, customer_email: str = None) -> str:
    """Generate QR code data string."""
    return f"TICKET:{ticket_id}:{customer_email or 'N/A'}"


def generate_ticket_pdf(
    ticket_id: str,
    customer_name: str,
    customer_email: str,
    ticket_type: str,
    quantity: int,
    price: float,
    currency: str,
    items: list = None,  # List of {"description": str, "quantity": int, "amount": float}
) -> tuple:
    """
    Generate a ticket PDF with QR code overlaid on background image.
    Returns: (pdf_bytes, pdf_base64_data)
    """
    try:
        # Generate QR code
        qrcode_data = generate_qrcode_data(ticket_id, customer_email)
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=2,
        )
        qr.add_data(qrcode_data)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")

        # Load background image
        try:
            bg_img = Image.open(BACKGROUND_PATH)
        except Exception:
            bg_img = Image.new("RGB", (1024, 1536), color="white")

        # Create a copy to avoid modifying original
        ticket_img = bg_img.copy()

        # Overlay QR code on background (top-right corner)
        qr_size = (200, 200)
        qr_img_resized = qr_img.resize(qr_size)
        ticket_img.paste(qr_img_resized, (ticket_img.width - qr_size[0] - 20, 20))

        # Add text overlay using PIL
        draw = ImageDraw.Draw(ticket_img)
        try:
            font_large = ImageFont.truetype("arial.ttf", 32)
            font_medium = ImageFont.truetype("arial.ttf", 24)
            font_small = ImageFont.truetype("arial.ttf", 16)
        except Exception:
            font_large = ImageFont.load_default()
            font_medium = ImageFont.load_default()
            font_small = ImageFont.load_default()

        text_color = (0, 0, 0)
        y_offset = 100

        # Add ticket info text
        draw.text((50, y_offset), f"Ticket: {ticket_id[:12]}", fill=text_color, font=font_medium)
        draw.text((50, y_offset + 60), f"Nome: {customer_name}", fill=text_color, font=font_medium)
        draw.text((50, y_offset + 120), f"Email: {customer_email}", fill=text_color, font=font_small)
        draw.text(
            (50, y_offset + 180),
            f"Tipo: {ticket_type}",
            fill=text_color,
            font=font_medium
        )
        draw.text(
            (50, y_offset + 240),
            f"Quantidade: {quantity}",
            fill=text_color,
            font=font_medium
        )
        draw.text(
            (50, y_offset + 300),
            f"Preço: {currency} {price:,.2f}",
            fill=text_color,
            font=font_large
        )

        # Add items if provided
        if items:
            y_offset += 380
            draw.text((50, y_offset), "Itens:", fill=text_color, font=font_medium)
            for idx, item in enumerate(items[:5]):  # Max 5 items
                desc = item.get("description", "Item")[:40]
                qty = item.get("quantity", 1)
                amount = item.get("amount", 0)
                draw.text(
                    (70, y_offset + 40 + idx * 40),
                    f"• {desc} x{qty} ({currency} {amount:,.2f})",
                    fill=text_color,
                    font=font_small
                )

        # Add date
        draw.text(
            (50, ticket_img.height - 80),
            f"Gerado: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            fill=text_color,
            font=font_small
        )

        # Save image as PDF (using reportlab for PDF format)
        pdf_buffer = BytesIO()
        c = canvas.Canvas(pdf_buffer, pagesize=letter)
        width, height = letter

        # Scale image to fit page
        img_width = width - 0.5 * inch
        img_height = (img_width * ticket_img.height) / ticket_img.width
        if img_height > height - 0.5 * inch:
            img_height = height - 0.5 * inch
            img_width = (img_height * ticket_img.width) / ticket_img.height

        # Save PIL image to BytesIO
        img_buffer = BytesIO()
        ticket_img.save(img_buffer, format="PNG")
        img_buffer.seek(0)

        # Draw on canvas
        c.drawImage(
            ImageReader(img_buffer),
            (width - img_width) / 2,
            height - img_height - 0.25 * inch,
            width=img_width,
            height=img_height
        )

        c.save()
        pdf_buffer.seek(0)

        pdf_bytes = pdf_buffer.getvalue()
        pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")

        log_pdf_generation(ticket_id, "success", file_size=len(pdf_bytes))
        return pdf_bytes, pdf_base64

    except Exception as exc:
        log_pdf_generation(ticket_id, "error", error=str(exc))
        raise
