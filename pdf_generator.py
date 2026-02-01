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
    items: list = None,
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

        # Add text overlay with improved centered layout
        draw = ImageDraw.Draw(ticket_img, 'RGBA')
        try:
            # Dependência: fontes Arial devem estar disponíveis no sistema; caso contrário, usa fonte padrão.
            font_title = ImageFont.truetype("arial.ttf", 40)
            font_large = ImageFont.truetype("arialbd.ttf", 36)
            font_medium = ImageFont.truetype("arial.ttf", 28)
            font_small = ImageFont.truetype("arial.ttf", 20)
        except Exception:
            font_title = ImageFont.load_default()
            font_large = ImageFont.load_default()
            font_medium = ImageFont.load_default()
            font_small = ImageFont.load_default()

        text_color = (0, 0, 0, 255)
        
        # Box semi-transparente centralizado
        box_width = 700
        box_x = (ticket_img.width - box_width) // 2
        box_y = 50
        
        # Box 1: Informações principais
        draw.rectangle(
            [(box_x, box_y), (box_x + box_width, box_y + 350)],
            fill=(255, 255, 255, 220)
        )
        
        # Título centralizado
        ticket_short = ticket_id[:12] + "..."
        title_text = f"Ticket: {ticket_short}"
        bbox = draw.textbbox((0, 0), title_text, font=font_title)
        title_width = bbox[2] - bbox[0]
        draw.text(
            ((ticket_img.width - title_width) // 2, box_y + 20),
            title_text,
            fill=text_color,
            font=font_title
        )
        
        # Nome
        name_text = f"Nome: {customer_name}"
        bbox = draw.textbbox((0, 0), name_text, font=font_medium)
        name_width = bbox[2] - bbox[0]
        draw.text(
            ((ticket_img.width - name_width) // 2, box_y + 90),
            name_text,
            fill=text_color,
            font=font_medium
        )
        
        # Email
        email_text = f"Email: {customer_email}"
        bbox = draw.textbbox((0, 0), email_text, font=font_small)
        email_width = bbox[2] - bbox[0]
        draw.text(
            ((ticket_img.width - email_width) // 2, box_y + 140),
            email_text,
            fill=text_color,
            font=font_small
        )
        
        # Tipo
        type_text = f"Tipo: {ticket_type}"
        bbox = draw.textbbox((0, 0), type_text, font=font_medium)
        type_width = bbox[2] - bbox[0]
        draw.text(
            ((ticket_img.width - type_width) // 2, box_y + 190),
            type_text,
            fill=text_color,
            font=font_medium
        )
        
        # Quantidade
        qty_text = f"Quantidade: {quantity}"
        bbox = draw.textbbox((0, 0), qty_text, font=font_medium)
        qty_width = bbox[2] - bbox[0]
        draw.text(
            ((ticket_img.width - qty_width) // 2, box_y + 240),
            qty_text,
            fill=text_color,
            font=font_medium
        )
        
        # Preço DESTACADO
        price_text = f"Preço: {currency} {price:,.2f}"
        bbox = draw.textbbox((0, 0), price_text, font=font_large)
        price_width = bbox[2] - bbox[0]
        draw.text(
            ((ticket_img.width - price_width) // 2, box_y + 290),
            price_text,
            fill=(204, 0, 0, 255),
            font=font_large
        )

        # Box 2: Itens
        if items:
            items_box_y = box_y + 400
            items_box_height = min(250, 50 + len(items[:5]) * 50)
            
            draw.rectangle(
                [(box_x, items_box_y), (box_x + box_width, items_box_y + items_box_height)],
                fill=(255, 255, 255, 220)
            )
            
            items_title = "Itens:"
            bbox = draw.textbbox((0, 0), items_title, font=font_medium)
            items_title_width = bbox[2] - bbox[0]
            draw.text(
                ((ticket_img.width - items_title_width) // 2, items_box_y + 15),
                items_title,
                fill=text_color,
                font=font_medium
            )
            
            for idx, item in enumerate(items[:5]):
                desc = item.get("description", "Item")[:40]
                qty_item = item.get("quantity", 1)
                amount = item.get("amount", 0)
                item_text = f"• {desc} x{qty_item} ({currency} {amount:,.2f})"
                bbox = draw.textbbox((0, 0), item_text, font=font_small)
                item_width = bbox[2] - bbox[0]
                draw.text(
                    ((ticket_img.width - item_width) // 2, items_box_y + 65 + idx * 45),
                    item_text,
                    fill=text_color,
                    font=font_small
                )

        # Data no rodapé
        date_text = f"Gerado: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        bbox = draw.textbbox((0, 0), date_text, font=font_small)
        date_width = bbox[2] - bbox[0]
        draw.text(
            ((ticket_img.width - date_width) // 2, ticket_img.height - 60),
            date_text,
            fill=text_color,
            font=font_small
        )

        # Save as PDF
        pdf_buffer = BytesIO()
        c = canvas.Canvas(pdf_buffer, pagesize=letter)
        width, height = letter

        img_width = width - 0.5 * inch
        img_height = (img_width * ticket_img.height) / ticket_img.width
        if img_height > height - 0.5 * inch:
            img_height = height - 0.5 * inch
            img_width = (img_height * ticket_img.width) / ticket_img.height

        img_buffer = BytesIO()
        ticket_img.save(img_buffer, format="PNG")
        img_buffer.seek(0)

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
