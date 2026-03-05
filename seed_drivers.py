"""
Seed script: crea usuarios con rol Repartidor para el sistema de rutas.

Uso:
    python seed_drivers.py              # dentro del entorno virtual
    docker-compose exec app python seed_drivers.py

Crea 3 repartidores activos si aún no existen (idempotente por username).
Contraseña inicial de todos: Repartidor2024!
"""

import sys
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from passlib.context import CryptContext

from app.config.settings import get_settings
from app.models.models import User, Role

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

REPARTIDORES = [
    {
        "username": "carlos.munoz",
        "email": "carlos.munoz@botilleria.cl",
        "password": "Repartidor2024!",
    },
    {
        "username": "pedro.soto",
        "email": "pedro.soto@botilleria.cl",
        "password": "Repartidor2024!",
    },
    {
        "username": "miguel.vargas",
        "email": "miguel.vargas@botilleria.cl",
        "password": "Repartidor2024!",
    },
]


def main():
    settings = get_settings()
    engine = create_engine(settings.database_url)

    print("\n Seed: Repartidores")
    print("─" * 50)

    with Session(engine) as db:
        # Obtener rol Repartidor
        rol = db.query(Role).filter(Role.role_name == "Repartidor").first()
        if not rol:
            print("❌  No existe el rol 'Repartidor' en la BD.")
            print("    Ejecuta primero: alembic upgrade head")
            sys.exit(1)

        print(f"✓  Rol encontrado: {rol.role_name} (id={rol.id})\n")

        created = 0
        skipped = 0

        for data in REPARTIDORES:
            existing = (
                db.query(User)
                .filter(User.username == data["username"])
                .first()
            )
            if existing:
                print(f"  ⚠️  {data['username']} ya existe — omitido")
                skipped += 1
                continue

            user = User(
                id=uuid.uuid4(),
                username=data["username"],
                email=data["email"],
                password_hash=pwd_context.hash(data["password"]),
                role_id=rol.id,
                active_status=True,
            )
            db.add(user)
            print(f"  ✅  {data['username']} <{data['email']}>")
            created += 1

        db.commit()

    print("─" * 50)
    print(f"\n✨  {created} repartidor(es) creados, {skipped} omitidos.")
    if created:
        print("    Contraseña inicial de todos: Repartidor2024!")
    print()


if __name__ == "__main__":
    main()
