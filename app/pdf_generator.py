import io
import os
import base64
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

LOGO_FALLBACK = "/9j/4AAQSkZJRgABAQAASABIAAD/4QCMRXhpZgAATU0AKgAAAAgABQESAAMAAAABAAEAAAEaAAUAAAABAAAASgEbAAUAAAABAAAAUgEoAAMAAAABAAIAAIdpAAQAAAABAAAAWgAAAAAAAABIAAAAAQAAAEgAAAABAAOgAQADAAAAAQABAACgAgAEAAAAAQAAAoCgAwAEAAAAAQAAAoAAAAAA/+0AOFBob3Rvc2hvcCAzLjAAOEJJTQQEAAAAAAAAOEJJTQQlAAAAAAAQ1B2M2Y8AsgTpgAmY7PhCfv/AABEIAoACgAMBIgACEQEDEQH/xAAfAAABBQEBAQEBAQAAAAAAAAAAAQIDBAUGBwgJCgv/xAC1EAACAQMDAgQDBQUEBAAAAX0BAgMABBEFEiExQQYTUWEHInEUMoGRoQgjQrHBFVLR8CQzYnKCCQoWFxgZGiUmJygpKjQ1Njc4OTpDREVGR0hJSlNUVVZXWFlaY2RlZmdoaWpzdHV2d3h5eoOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4eLj5OXm5+jp6vHy8/T19vf4+fr/xAAfAQADAQEBAQEBAQEBAAAAAAAAAQIDBAUGBwgJCgv/xAC1EQACAQIEBAMEBwUEBAABAncAAQIDEQQFITEGEkFRB2FxEyIxgUQUQpGhscE/9oADAMBAAIRACEQEDEQH/AP9k="

def generar_factura_pdf(venta, items):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    elements = []

    if os.path.exists("static/logo.png"):
        logo_image = Image("static/logo.png", width=1.4*inch, height=1.4*inch)
    else:
        logo_data = base64.b64decode(LOGO_FALLBACK)
        logo_image = Image(io.BytesIO(logo_data), width=1.4*inch, height=1.4*inch)

    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=18, textColor=colors.HexColor('#6F4E37'), alignment=1)
    normal_style = styles['Normal']

    num_factura = venta.get("consecutivo_str", str(venta.get("_id", ""))[:8])

    elements.append(logo_image)
    elements.append(Spacer(1, 6))
    elements.append(Paragraph("0808 CAFÉ DE ESPECIALIDAD", title_style))
    elements.append(Spacer(1, 15))

    info_data = [
        [Paragraph(f"<b>Factura N°:</b> {num_factura}", normal_style), Paragraph(f"<b>Fecha:</b> {venta['fecha']}", normal_style)],
        [Paragraph(f"<b>Cliente:</b> {venta.get('cliente', 'General')}", normal_style), Paragraph(f"<b>Método:</b> {venta['tipo_pago']}", normal_style)]
    ]
    elements.append(Table(info_data, colWidths=[3.5*inch, 3.5*inch]))
    elements.append(Spacer(1, 15))

    table_data = [["Producto", "Cant.", "Precio Unit.", "Descuento", "Subtotal"]]
    for item in items:
        cant = item["cantidad"]
        desc_unitario = item.get("descuento", 0)
        desc_total = desc_unitario * cant

        table_data.append([
            f"{item['nombre']} ({int(item['gramaje'])}g)",
            str(cant),
            f"${int(item['precio_unitario']):,}",
            f"${int(desc_total):,}",
            f"${int(item['subtotal']):,}"
        ])

    prod_table = Table(table_data, colWidths=[3.0*inch, 0.7*inch, 1.1*inch, 1.1*inch, 1.1*inch])
    prod_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#6F4E37')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E0D5C5')),
        ('ALIGN', (1,0), (-1,-1), 'CENTER'),
    ]))
    elements.append(prod_table)
    elements.append(Spacer(1, 15))

    total_data = [["", "TOTAL PAGADO:", f"${int(venta['total_venta']):,} COP"]]
    elements.append(Table(total_data, colWidths=[3.0*inch, 2.2*inch, 1.8*inch]))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()
