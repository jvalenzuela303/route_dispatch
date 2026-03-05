#!/usr/bin/env python3
"""
Diagnostic script for authentication issues
Run inside the container: docker-compose exec app python diagnose_auth.py
Or locally with venv activated: python diagnose_auth.py
"""
import sys
sys.path.insert(0, '/app')  # For Docker
sys.path.insert(0, '.')     # For local

try:
    from app.config.database import get_db_context
    from app.models.models import User, Role, RefreshToken
    from passlib.context import CryptContext
    import bcrypt

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    print("=" * 60)
    print("DIAGNOSTIC: Authentication Issues")
    print("=" * 60)

    with get_db_context() as db:
        # 1. Check if tables exist
        print("\n1. Checking tables...")
        try:
            users = db.query(User).count()
            print(f"   ✓ Users table exists ({users} users)")
        except Exception as e:
            print(f"   ✗ Users table error: {e}")

        try:
            roles = db.query(Role).count()
            print(f"   ✓ Roles table exists ({roles} roles)")
        except Exception as e:
            print(f"   ✗ Roles table error: {e}")

        try:
            tokens = db.query(RefreshToken).count()
            print(f"   ✓ RefreshTokens table exists ({tokens} tokens)")
        except Exception as e:
            print(f"   ✗ RefreshTokens table error: {e}")

        # 2. Check admin user
        print("\n2. Checking admin user...")
        admin = db.query(User).filter(
            (User.username == 'admin') | (User.email == 'admin@botilleria.cl')
        ).first()

        if admin:
            print(f"   ✓ Admin user found:")
            print(f"     - ID: {admin.id}")
            print(f"     - Username: {admin.username}")
            print(f"     - Email: {admin.email}")
            print(f"     - Active: {admin.active_status}")
            print(f"     - Role ID: {admin.role_id}")
            print(f"     - Password hash (first 30 chars): {admin.password_hash[:30]}...")

            # 3. Check role relationship
            print("\n3. Checking role relationship...")
            try:
                role = admin.role
                print(f"   ✓ Role loaded: {role.role_name}")
            except Exception as e:
                print(f"   ✗ Role error: {e}")

            # 4. Test password verification
            print("\n4. Testing password verification...")
            test_password = "Test1234!"

            # Method 1: passlib
            try:
                result1 = pwd_context.verify(test_password, admin.password_hash)
                print(f"   Passlib verify: {'✓ PASS' if result1 else '✗ FAIL'}")
            except Exception as e:
                print(f"   Passlib error: {e}")

            # Method 2: bcrypt direct
            try:
                result2 = bcrypt.checkpw(
                    test_password.encode('utf-8'),
                    admin.password_hash.encode('utf-8')
                )
                print(f"   BCrypt verify: {'✓ PASS' if result2 else '✗ FAIL'}")
            except Exception as e:
                print(f"   BCrypt error: {e}")

            # 5. Check hash format
            print("\n5. Checking hash format...")
            hash_prefix = admin.password_hash[:7]
            print(f"   Hash prefix: {hash_prefix}")
            if hash_prefix.startswith('$2b$') or hash_prefix.startswith('$2a$'):
                print("   ✓ Valid bcrypt format")
            else:
                print("   ✗ Invalid bcrypt format!")

            # 6. Test creating a new hash and comparing
            print("\n6. Testing new hash creation...")
            new_hash = pwd_context.hash(test_password)
            print(f"   New hash prefix: {new_hash[:7]}")
            verify_new = pwd_context.verify(test_password, new_hash)
            print(f"   New hash verify: {'✓ PASS' if verify_new else '✗ FAIL'}")

        else:
            print("   ✗ Admin user NOT FOUND!")
            print("\n   Available users:")
            for u in db.query(User).all():
                print(f"     - {u.username} ({u.email})")

    print("\n" + "=" * 60)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 60)

except Exception as e:
    print(f"\nFATAL ERROR: {e}")
    import traceback
    traceback.print_exc()
