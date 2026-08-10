import io
import os
import base64
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

LOGO_FALLBACK = "/9j/4AAQSkZJRgABAQAASABIAAD/4QCMRXhpZgAATU0AKgAAAAgABQESAAMAAAABAAEAAAEaAAUAAAABAAAASgEbAAUAAAABAAAAUgEoAAMAAAABAAIAAIdpAAQAAAABAAAAWgAAAAAAAABIAAAAAQAAAEgAAAABAAOgAQADAAAAAQABAACgAgAEAAAAAQAAAoCgAwAEAAAAAQAAAoAAAAAA/+0AOFBob3Rvc2hvcCAzLjAAOEJJTQQEAAAAAAAAOEJJTQQlAAAAAAAQ1B2M2Y8AsgTpgAmY7PhCfv/AABEIAoACgAMBIgACEQEDEQH/xAAfAAABBQEBAQEBAQAAAAAAAAAAAQIDBAUGBwgJCgv/xAC1EAACAQMDAgQDBQUEBAAAAX0BAgMABBEFEiExQQYTUWEHInEUMoGRoQgjQrHBFVLR8CQzYnKCCQoWFxgZGiUmJygpKjQ1Njc4OTpDREVGR0hJSlNUVVZXWFlaY2RlZmdoaWpzdHV2d3h5eoOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4eLj5OXm5+jp6vHy8/T19vf4+fr/xAAfAQADAQEBAQEBAQEBAAAAAAAAAQIDBAUGBwgJCgv/xAC1EQACAQIEBAMEBwUEBAABAncAAQIDEQQFITEGEkFRB2FxEyIxgUQUQpGhscE/9oADAMBAAIRACEQEDEQH/AP9k="

def generar_factura_pdf(documento, items, es_cotizacion=False):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    elements = []

    logo_path = "static/logo_factura.jpeg"
    if not os.path.exists(logo_path):
        logo_path = "static/logo.png"

    if os.path.exists(logo_path):
        # Se incrementa el tamaño del logo a 2.2 pulgadas
        logo_image = Image(logo_path, width=2.2*inch, height=2.2*inch)
    else:
        logo_data = base64.b64decode(LOGO_FALLBACK)
        logo_image = Image(io.BytesIO(logo_data), width=2.2*inch, height=2.2*inch)

    # Estilos en NEGRO
    title_style = ParagraphStyle(
        'TitleStyle', 
        parent=styles['Heading1'], 
        fontName='Helvetica-Bold', 
        fontSize=20, 
        textColor=colors.black, 
        alignment=1
    )
    normal_style = ParagraphStyle(
        'NormalBlack',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        textColor=colors.black
    )
    account_style = ParagraphStyle(
        'AccountStyle', 
        parent=styles['Normal'], 
        fontName='Helvetica', 
        fontSize=9, 
        leading=13, 
        textColor=colors.black
    )

    num_doc = documento.get("consecutivo_str", str(documento.get("_id", ""))[:8])
    tipo_doc_titulo = "COTIZACIÓN" if es_cotizacion else "FACTURA DE VENTA"
    label_num = "Cotización N°:" if es_cotizacion else "Factura N°:"

    elements.append(logo_image)
    elements.append(Spacer(1, 6))
    elements.append(Paragraph("0808 CAFÉ DE ESPECIALIDAD", title_style))
    elements.append(Paragraph(f"<b>{tipo_doc_titulo}</b>", ParagraphStyle('SubTitle', parent=normal_style, alignment=1, fontSize=12)))
    elements.append(Spacer(1, 15))

    info_data = [
        [Paragraph(f"<b>{label_num}</b> {num_doc}", normal_style), Paragraph(f"<b>Fecha:</b> {documento['fecha']}", normal_style)],
        [Paragraph(f"<b>Cliente:</b> {documento.get('cliente', 'General')}", normal_style), Paragraph(f"<b>Método:</b> {documento.get('tipo_pago', 'N/A')}", normal_style)]
    ]
    elements.append(Table(info_data, colWidths=[3.5*inch, 3.5*inch]))
    elements.append(Spacer(1, 15))

    table_data = [["Producto", "Cant.", "Precio Unit.", "Descuento", "Subtotal"]]
    
    valor_total_bruto = 0.0
    descuento_total = 0.0

    for item in items:
        cant = item["cantidad"]
        p_unit = item["precio_unitario"]
        desc_u = item.get("descuento", 0.0)
        pres = item.get("presentacion", "Grano")

        subtotal_bruto = cant * p_unit
        desc_item_total = desc_u * cant

        valor_total_bruto += subtotal_bruto
        descuento_total += desc_item_total

        table_data.append([
            f"{item['nombre']} ({int(item['gramaje'])}g - {pres})",
            str(cant),
            f"${int(p_unit):,}",
            f"${int(desc_item_total):,}",
            f"${int(subtotal_bruto):,}"
        ])

    valor_a_pagar = max(0.0, valor_total_bruto - descuento_total) if documento.get("tipo_venta") != "Obsequio" else 0.0

    prod_table = Table(table_data, colWidths=[3.0*inch, 0.7*inch, 1.1*inch, 1.1*inch, 1.1*inch])
    prod_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.black),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#333333')),
        ('ALIGN', (1,0), (-1,-1), 'CENTER'),
        ('TEXTCOLOR', (0,1), (-1,-1), colors.black),
    ]))
    elements.append(prod_table)
    elements.append(Spacer(1, 15))

    texto_cuenta = Paragraph(
        "<b>Datos de Pago:</b><br/>"
        "Cuenta de Ahorros<br/>"
        "Bancolombia No 333-998815-66<br/>"
        "Amaia Sierra",
        account_style
    )

    total_data = [
        [texto_cuenta, "Valor Total:", f"${int(valor_total_bruto):,} COP"],
        ["", "Descuento Total:", f"-${int(descuento_total):,} COP"],
        ["", "Valor a Pagar:", f"${int(valor_a_pagar):,} COP"]
    ]

    t_totales = Table(total_data, colWidths=[3.2*inch, 2.0*inch, 1.8*inch])
    t_totales.setStyle(TableStyle([
        ('SPAN', (0,0), (0,2)),
        ('VALIGN', (0,0), (0,2), 'TOP'),
        ('ALIGN', (0,0), (0,2), 'LEFT'),
        ('ALIGN', (1,0), (-1,-1), 'RIGHT'),
        ('FONTNAME', (1,2), (-1,2), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0,0), (-1,-1), colors.black),
    ]))
    elements.append(t_totales)

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()
