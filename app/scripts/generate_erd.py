"""
Entity Relationship Diagram (ERD) Generator

Generates a visual ERD from SQLAlchemy models showing:
- All tables and their columns
- Primary keys and foreign keys
- Relationships between tables
- Data types

Usage:
    python -m app.scripts.generate_erd

Output:
    Saves ERD to /home/juan/Desarrollo/route_dispatch/docs/erd.png
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, '/home/juan/Desarrollo/route_dispatch')

from eralchemy2 import render_er

from app.config.settings import get_settings
from app.models.base import Base


def generate_erd():
    """Generate ERD from SQLAlchemy models"""
    print("=" * 70)
    print("Generating Entity Relationship Diagram (ERD)")
    print("=" * 70)

    # Get database URL from settings
    settings = get_settings()
    database_url = settings.database_url

    # Output file path
    output_file = Path("/home/juan/Desarrollo/route_dispatch/docs/erd.png")
    output_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Generate ERD from database connection
        # This will show actual database structure
        print(f"\nConnecting to database: {database_url.split('@')[1]}")
        print("Generating diagram...")

        render_er(
            database_url,
            str(output_file)
        )

        print(f"\nERD successfully generated!")
        print(f"Location: {output_file}")
        print(f"Size: {output_file.stat().st_size / 1024:.2f} KB")

        # Also generate a PDF version
        pdf_file = output_file.with_suffix('.pdf')
        render_er(database_url, str(pdf_file))
        print(f"\nPDF version also generated: {pdf_file}")

        print("\n" + "=" * 70)
        print("ERD Generation Complete!")
        print("=" * 70)

    except Exception as e:
        print(f"\nError generating ERD: {e}")
        print("\nNote: Make sure the database is running and migrations have been applied.")
        print("Run: docker-compose up -d postgres")
        print("Then: alembic upgrade head")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    generate_erd()
