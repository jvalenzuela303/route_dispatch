"""
Seed script: crea pedidos en estado DOCUMENTADO listos para generar ruta.

Uso:
    python seed_orders.py [YYYY-MM-DD]

Si no se pasa fecha, usa HOY.
"""

import sys
import uuid
from datetime import datetime, timezone, date as date_type
from decimal import Decimal

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.models.models import Order, Invoice, User, Role
from app.models.enums import OrderStatus, SourceChannel, GeocodingConfidence, InvoiceType

# ─────────────────────────────────────────────────────────
# Pedidos con coordenadas reales de Rancagua y Machalí
# (lat, lon en WGS84)
# ─────────────────────────────────────────────────────────
PEDIDOS = [
    {
        "customer_name": "Juan Pérez González",
        "customer_phone": "+56912345678",
        "customer_email": "juan.perez@gmail.com",
        "address_text": "Avenida Brasil 875, Rancagua",
        "lat": -34.1709,
        "lon": -70.7372,
        "amount": 24900,
        "notes": "Entregar en horario de tarde",
    },
    {
        "customer_name": "María López Soto",
        "customer_phone": "+56923456789",
        "customer_email": "maria.lopez@hotmail.com",
        "address_text": "Calle Astorga 456, Rancagua",
        "lat": -34.1652,
        "lon": -70.7401,
        "amount": 15990,
        "notes": None,
    },
    {
        "customer_name": "Carlos Muñoz Vera",
        "customer_phone": "+56934567890",
        "customer_email": None,
        "address_text": "Pasaje Las Rosas 123, Machalí",
        "lat": -34.1801,
        "lon": -70.6951,
        "amount": 38500,
        "notes": "Llamar antes de llegar",
    },
    {
        "customer_name": "Ana Torres Díaz",
        "customer_phone": "+56945678901",
        "customer_email": "ana.torres@gmail.com",
        "address_text": "Avenida Cachapoal 1200, Rancagua",
        "lat": -34.1550,
        "lon": -70.7450,
        "amount": 9990,
        "notes": None,
    },
    {
        "customer_name": "Roberto Silva Morales",
        "customer_phone": "+56956789012",
        "customer_email": "roberto.silva@empresa.cl",
        "address_text": "Calle Millán 780, Rancagua",
        "lat": -34.1750,
        "lon": -70.7300,
        "amount": 52000,
        "notes": "Factura a nombre de empresa",
    },
    {
        "customer_name": "Patricia Fuentes Rojas",
        "customer_phone": "+56967890123",
        "customer_email": None,
        "address_text": "San Martín 345, Rancagua",
        "lat": -34.1690,
        "lon": -70.7440,
        "amount": 18700,
        "notes": None,
    },
]


def get_delivery_date() -> date_type:
    """Retorna la fecha de entrega: argumento CLI o hoy."""
    if len(sys.argv) > 1:
        try:
            return date_type.fromisoformat(sys.argv[1])
        except ValueError:
            print(f"⚠️  Fecha inválida '{sys.argv[1]}', usando HOY.")
    return date_type.today()


def main():
    settings = get_settings()
    engine = create_engine(settings.database_url)
    delivery_date = get_delivery_date()

    print(f"\n🗓️  Fecha de entrega: {delivery_date}")
    print("─" * 50)

    with Session(engine) as db:
        # ── Obtener el primer usuario admin disponible ──────────
        admin_user = (
            db.query(User)
            .join(Role)
            .filter(Role.role_name == "Administrador")
            .first()
        )
        if not admin_user:
            # Fallback: cualquier usuario activo
            admin_user = db.query(User).filter(User.active_status == True).first()

        if not admin_user:
            print("❌  No hay usuarios en la base de datos. Ejecuta las migraciones primero.")
            sys.exit(1)

        print(f"👤 Creando pedidos como usuario: {admin_user.username} ({admin_user.email})")
        print("─" * 50)

        created = 0
        for idx, data in enumerate(PEDIDOS, start=1):
            order_number = f"ORD-{delivery_date.strftime('%Y%m%d')}-S{idx:03d}"

            # Verificar si ya existe
            existing = db.query(Order).filter(Order.order_number == order_number).first()
            if existing:
                print(f"  ⚠️  {order_number} ya existe — omitido")
                continue

            # ── Crear Order ────────────────────────────────────
            order = Order(
                id=uuid.uuid4(),
                order_number=order_number,
                customer_name=data["customer_name"],
                customer_phone=data["customer_phone"],
                customer_email=data.get("customer_email"),
                address_text=data["address_text"],
                order_status=OrderStatus.DOCUMENTADO,
                source_channel=SourceChannel.WEB,
                delivery_date=delivery_date,
                geocoding_confidence=GeocodingConfidence.HIGH,
                created_by_user_id=admin_user.id,
                notes=data.get("notes"),
            )
            db.add(order)
            db.flush()  # obtener order.id antes de crear invoice

            # Insertar coordenadas PostGIS directamente con ST_GeomFromText
            db.execute(
                text(
                    "UPDATE orders SET address_coordinates = "
                    "ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography "
                    "WHERE id = :order_id"
                ),
                {"lon": data["lon"], "lat": data["lat"], "order_id": order.id},
            )

            # ── Crear Invoice (requisito para DOCUMENTADO) ─────
            invoice_number = f"BOL-{delivery_date.strftime('%Y%m%d')}-S{idx:03d}"
            invoice = Invoice(
                id=uuid.uuid4(),
                invoice_number=invoice_number,
                order_id=order.id,
                invoice_type=InvoiceType.BOLETA,
                total_amount=Decimal(str(data["amount"])),
                issued_at=datetime.now(timezone.utc),
                created_by_user_id=admin_user.id,
            )
            db.add(invoice)

            print(
                f"  ✅ {order_number} | {data['customer_name']:<22} | "
                f"{data['address_text'][:35]:<35} | ${data['amount']:>7,}"
            )
            created += 1

        db.commit()

    print("─" * 50)
    print(f"\n✨ {created} pedido(s) creados en estado DOCUMENTADO para {delivery_date}")
    print(f"   Listos para generar ruta en: http://localhost:3001/routes/generate\n")


if __name__ == "__main__":
    main()
