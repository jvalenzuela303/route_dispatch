"""
Email templates for customer notifications

This module provides HTML and plain text email templates for various
customer notifications, primarily for order status updates.

Templates are designed to be:
- Responsive (mobile-friendly)
- Professional and branded
- Accessible with plain text fallbacks
- Clear and actionable for customers
"""

from datetime import date
from typing import Tuple, Optional
from app.models.models import Order


def render_order_in_transit_email(order: Order) -> Tuple[str, str]:
    """
    Render email template for order in transit notification

    This template is sent when an order transitions to EN_RUTA status,
    informing the customer that their order is on the way.

    Args:
        order: Order instance with relationships loaded
              (must include assigned_route with assigned_driver)

    Returns:
        Tuple[str, str]: (html_body, plain_text_body)

    Raises:
        AttributeError: If required order fields are missing

    Example:
        >>> order = db.query(Order).filter(Order.id == order_id).first()
        >>> html, plain = render_order_in_transit_email(order)
        >>> email_service.send_email(order.customer_email, "Order in transit", html, plain)
    """
    # Extract order data safely
    order_number = order.order_number
    customer_name = order.customer_name

    # Format delivery date
    delivery_date_str = "Hoy"
    if order.delivery_date:
        delivery_date_str = _format_delivery_date(order.delivery_date)

    # Get driver name from route if available
    driver_name = "Nuestro repartidor"
    if order.assigned_route and order.assigned_route.assigned_driver:
        driver_name = order.assigned_route.assigned_driver.username

    # Extract customer address
    customer_address = order.address_text or "Dirección registrada"

    # HTML template - responsive and professional
    html_body = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Tu pedido está en camino</title>
    <style>
        body {{
            margin: 0;
            padding: 0;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333333;
            background-color: #f4f4f4;
        }}
        .email-container {{
            max-width: 600px;
            margin: 0 auto;
            background-color: #ffffff;
        }}
        .header {{
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
            color: #ffffff;
            padding: 40px 30px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 28px;
            font-weight: 600;
        }}
        .header .icon {{
            font-size: 48px;
            margin-bottom: 10px;
        }}
        .content {{
            padding: 40px 30px;
            background-color: #ffffff;
        }}
        .greeting {{
            font-size: 18px;
            margin-bottom: 20px;
            color: #333333;
        }}
        .message {{
            font-size: 16px;
            margin-bottom: 30px;
            color: #555555;
        }}
        .info-box {{
            background-color: #f8f9fa;
            border-left: 4px solid #11998e;
            padding: 20px;
            margin: 25px 0;
            border-radius: 4px;
        }}
        .info-row {{
            margin: 12px 0;
            font-size: 15px;
        }}
        .info-label {{
            font-weight: 600;
            color: #333333;
            display: inline-block;
            min-width: 140px;
        }}
        .info-value {{
            color: #555555;
        }}
        .cta-section {{
            text-align: center;
            margin: 30px 0;
            padding: 20px;
            background-color: #f0f9ff;
            border-radius: 8px;
        }}
        .cta-text {{
            font-size: 16px;
            color: #0369a1;
            font-weight: 500;
            margin: 0;
        }}
        .footer {{
            background-color: #2d3748;
            color: #a0aec0;
            padding: 30px;
            text-align: center;
            font-size: 14px;
        }}
        .footer-brand {{
            font-size: 18px;
            font-weight: 600;
            color: #ffffff;
            margin-bottom: 10px;
        }}
        .footer-text {{
            margin: 5px 0;
            color: #a0aec0;
        }}
        .footer-disclaimer {{
            margin-top: 15px;
            font-size: 12px;
            font-style: italic;
            color: #718096;
        }}
        @media only screen and (max-width: 600px) {{
            .header {{
                padding: 30px 20px;
            }}
            .header h1 {{
                font-size: 24px;
            }}
            .content {{
                padding: 30px 20px;
            }}
            .info-label {{
                min-width: auto;
                display: block;
                margin-bottom: 4px;
            }}
        }}
    </style>
</head>
<body>
    <div class="email-container">
        <!-- Header -->
        <div class="header">
            <div class="icon">🚚</div>
            <h1>¡Tu pedido está en camino!</h1>
        </div>

        <!-- Content -->
        <div class="content">
            <div class="greeting">
                Hola <strong>{customer_name}</strong>,
            </div>

            <div class="message">
                Te informamos que tu pedido <strong>#{order_number}</strong> ya está en ruta
                y pronto llegará a tu domicilio. Nuestro repartidor está en camino para entregarte tu compra.
            </div>

            <!-- Order Details -->
            <div class="info-box">
                <div class="info-row">
                    <span class="info-label">📦 Número de pedido:</span>
                    <span class="info-value">{order_number}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">📅 Fecha de entrega:</span>
                    <span class="info-value">{delivery_date_str}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">🚗 Repartidor:</span>
                    <span class="info-value">{driver_name}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">📍 Dirección:</span>
                    <span class="info-value">{customer_address}</span>
                </div>
            </div>

            <!-- Call to Action -->
            <div class="cta-section">
                <p class="cta-text">
                    Por favor, asegúrate de estar disponible en la dirección indicada
                    para recibir tu pedido.
                </p>
            </div>

            <div class="message">
                Si tienes alguna pregunta o necesitas realizar algún cambio,
                no dudes en contactarnos.
            </div>

            <div class="message" style="margin-top: 30px; font-weight: 500;">
                ¡Gracias por tu compra! 🎉
            </div>
        </div>

        <!-- Footer -->
        <div class="footer">
            <div class="footer-brand">Botillería Rancagua</div>
            <div class="footer-text">Tu proveedor de confianza en Rancagua</div>
            <div class="footer-text">📞 Contáctanos: +56 9 XXXX XXXX</div>
            <div class="footer-disclaimer">
                Este es un correo automático, por favor no responder directamente a este mensaje.
            </div>
        </div>
    </div>
</body>
</html>"""

    # Plain text fallback - accessible and clean
    plain_text_body = f"""
========================================
¡TU PEDIDO ESTÁ EN CAMINO!
========================================

Hola {customer_name},

Te informamos que tu pedido #{order_number} ya está en ruta y pronto llegará a tu domicilio.

DETALLES DEL PEDIDO:
--------------------
Número de pedido: {order_number}
Fecha de entrega: {delivery_date_str}
Repartidor: {driver_name}
Dirección: {customer_address}

Por favor, asegúrate de estar disponible en la dirección indicada para recibir tu pedido.

Si tienes alguna pregunta o necesitas realizar algún cambio, no dudes en contactarnos.

¡Gracias por tu compra!

========================================
Botillería Rancagua
Tu proveedor de confianza en Rancagua
Contacto: +56 9 XXXX XXXX
========================================

Este es un correo automático, por favor no responder directamente a este mensaje.
"""

    return html_body.strip(), plain_text_body.strip()


def _format_delivery_date(delivery_date: date) -> str:
    """
    Format delivery date in Spanish locale

    Args:
        delivery_date: Date object to format

    Returns:
        str: Formatted date string (e.g., "Martes 21 de Enero, 2026")

    Examples:
        >>> from datetime import date
        >>> _format_delivery_date(date(2026, 1, 21))
        'Martes 21 de Enero, 2026'
    """
    # Spanish day names
    days = {
        0: "Lunes",
        1: "Martes",
        2: "Miércoles",
        3: "Jueves",
        4: "Viernes",
        5: "Sábado",
        6: "Domingo"
    }

    # Spanish month names
    months = {
        1: "Enero",
        2: "Febrero",
        3: "Marzo",
        4: "Abril",
        5: "Mayo",
        6: "Junio",
        7: "Julio",
        8: "Agosto",
        9: "Septiembre",
        10: "Octubre",
        11: "Noviembre",
        12: "Diciembre"
    }

    day_name = days[delivery_date.weekday()]
    month_name = months[delivery_date.month]

    return f"{day_name} {delivery_date.day} de {month_name}, {delivery_date.year}"


def render_delivery_confirmed_email(order: Order) -> Tuple[str, str]:
    """
    Render email template for delivery confirmation

    This template can be used when order transitions to ENTREGADO status.
    Currently a placeholder for future implementation.

    Args:
        order: Order instance

    Returns:
        Tuple[str, str]: (html_body, plain_text_body)
    """
    # Placeholder for future implementation
    html_body = f"""
    <html>
    <body>
        <h1>Pedido Entregado</h1>
        <p>Hola {order.customer_name},</p>
        <p>Tu pedido #{order.order_number} ha sido entregado exitosamente.</p>
        <p>¡Gracias por tu compra!</p>
    </body>
    </html>
    """

    plain_text_body = f"""
    Pedido Entregado

    Hola {order.customer_name},

    Tu pedido #{order.order_number} ha sido entregado exitosamente.

    ¡Gracias por tu compra!
    """

    return html_body.strip(), plain_text_body.strip()
