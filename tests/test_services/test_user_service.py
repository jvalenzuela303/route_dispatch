"""
Tests for UserService

This module tests all user management operations including:
- User creation
- User retrieval and listing
- User updates
- User deletion (soft delete)
- Password management
- RBAC enforcement
"""

import pytest
from uuid import uuid4

from app.services.user_service import UserService
from app.services.auth_service import AuthService
from app.models.models import User, Role
from app.exceptions import (
    NotFoundError,
    UserAlreadyExistsError,
    InsufficientPermissionsError,
    WeakPasswordError,
    InvalidCredentialsError
)


@pytest.fixture
def user_service(db_session):
    """Create UserService instance for testing"""
    return UserService(db_session)


@pytest.fixture
def admin_role(db_session):
    """Create admin role"""
    role = Role(
        role_name="Administrador",
        description="Administrator with full access",
        permissions={"can_create_user": True, "can_override": True}
    )
    db_session.add(role)
    db_session.commit()
    db_session.refresh(role)
    return role


@pytest.fixture
def vendedor_role(db_session):
    """Create vendedor role"""
    role = Role(
        role_name="Vendedor",
        description="Sales person",
        permissions={"can_create_order": True}
    )
    db_session.add(role)
    db_session.commit()
    db_session.refresh(role)
    return role


@pytest.fixture
def encargado_role(db_session):
    """Create warehouse manager role"""
    role = Role(
        role_name="Encargado Bodega",
        description="Warehouse manager",
        permissions={"can_generate_route": True}
    )
    db_session.add(role)
    db_session.commit()
    db_session.refresh(role)
    return role


@pytest.fixture
def admin_user(db_session, admin_role):
    """Create admin user"""
    user = User(
        username="admin",
        email="admin@test.com",
        password_hash=AuthService.hash_password("AdminPass123"),
        role_id=admin_role.id,
        active_status=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def vendedor_user(db_session, vendedor_role):
    """Create vendedor user"""
    user = User(
        username="vendedor",
        email="vendedor@test.com",
        password_hash=AuthService.hash_password("VendedorPass123"),
        role_id=vendedor_role.id,
        active_status=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


class TestCreateUser:
    """Tests for user creation"""

    def test_create_user_success(self, user_service, admin_user, vendedor_role):
        """Test successful user creation by admin"""
        new_user = user_service.create_user(
            username="newuser",
            email="newuser@test.com",
            password="NewUserPass123",
            role_id=vendedor_role.id,
            created_by=admin_user
        )

        assert new_user is not None
        assert new_user.username == "newuser"
        assert new_user.email == "newuser@test.com"
        assert new_user.role_id == vendedor_role.id
        assert new_user.active_status is True
        # Password should be hashed, not plaintext
        assert new_user.password_hash != "NewUserPass123"

    def test_create_user_permission_denied(self, user_service, vendedor_user, vendedor_role):
        """Test that non-admin cannot create user"""
        with pytest.raises(InsufficientPermissionsError) as exc_info:
            user_service.create_user(
                username="newuser",
                email="newuser@test.com",
                password="NewUserPass123",
                role_id=vendedor_role.id,
                created_by=vendedor_user
            )

        assert "Administrador" in str(exc_info.value)

    def test_create_user_duplicate_username(self, user_service, admin_user, vendedor_user, vendedor_role):
        """Test creation with duplicate username"""
        with pytest.raises(UserAlreadyExistsError) as exc_info:
            user_service.create_user(
                username=vendedor_user.username,
                email="different@test.com",
                password="NewUserPass123",
                role_id=vendedor_role.id,
                created_by=admin_user
            )

        assert "username" in str(exc_info.value).lower()

    def test_create_user_duplicate_email(self, user_service, admin_user, vendedor_user, vendedor_role):
        """Test creation with duplicate email"""
        with pytest.raises(UserAlreadyExistsError) as exc_info:
            user_service.create_user(
                username="differentusername",
                email=vendedor_user.email,
                password="NewUserPass123",
                role_id=vendedor_role.id,
                created_by=admin_user
            )

        assert "email" in str(exc_info.value).lower()

    def test_create_user_weak_password_short(self, user_service, admin_user, vendedor_role):
        """Test creation with password too short"""
        with pytest.raises(WeakPasswordError) as exc_info:
            user_service.create_user(
                username="newuser",
                email="newuser@test.com",
                password="Short1",  # Only 6 characters
                role_id=vendedor_role.id,
                created_by=admin_user
            )

        assert "8 characters" in str(exc_info.value)

    def test_create_user_weak_password_no_uppercase(self, user_service, admin_user, vendedor_role):
        """Test creation with password missing uppercase"""
        with pytest.raises(WeakPasswordError) as exc_info:
            user_service.create_user(
                username="newuser",
                email="newuser@test.com",
                password="lowercase123",
                role_id=vendedor_role.id,
                created_by=admin_user
            )

        assert "uppercase" in str(exc_info.value).lower()

    def test_create_user_weak_password_no_lowercase(self, user_service, admin_user, vendedor_role):
        """Test creation with password missing lowercase"""
        with pytest.raises(WeakPasswordError) as exc_info:
            user_service.create_user(
                username="newuser",
                email="newuser@test.com",
                password="UPPERCASE123",
                role_id=vendedor_role.id,
                created_by=admin_user
            )

        assert "lowercase" in str(exc_info.value).lower()

    def test_create_user_weak_password_no_digit(self, user_service, admin_user, vendedor_role):
        """Test creation with password missing digit"""
        with pytest.raises(WeakPasswordError) as exc_info:
            user_service.create_user(
                username="newuser",
                email="newuser@test.com",
                password="NoDigitsHere",
                role_id=vendedor_role.id,
                created_by=admin_user
            )

        assert "digit" in str(exc_info.value).lower()

    def test_create_user_invalid_role(self, user_service, admin_user):
        """Test creation with non-existent role"""
        with pytest.raises(NotFoundError) as exc_info:
            user_service.create_user(
                username="newuser",
                email="newuser@test.com",
                password="ValidPass123",
                role_id=uuid4(),
                created_by=admin_user
            )

        assert "Role" in str(exc_info.value)


class TestGetUser:
    """Tests for user retrieval"""

    def test_get_user_success(self, user_service, admin_user, vendedor_user):
        """Test successful user retrieval"""
        user = user_service.get_user(vendedor_user.id, admin_user)

        assert user is not None
        assert user.id == vendedor_user.id
        assert user.username == vendedor_user.username

    def test_get_user_not_found(self, user_service, admin_user):
        """Test retrieval of non-existent user"""
        with pytest.raises(NotFoundError):
            user_service.get_user(uuid4(), admin_user)

    def test_get_user_own_profile(self, user_service, vendedor_user):
        """Test user can view their own profile"""
        user = user_service.get_user(vendedor_user.id, vendedor_user)

        assert user.id == vendedor_user.id

    def test_get_user_other_profile_denied(self, user_service, vendedor_user, admin_user):
        """Test vendedor cannot view other user profiles"""
        with pytest.raises(InsufficientPermissionsError):
            user_service.get_user(admin_user.id, vendedor_user)


class TestListUsers:
    """Tests for user listing"""

    def test_list_users_admin(self, user_service, admin_user, vendedor_user):
        """Test admin can list users"""
        users = user_service.list_users(admin_user)

        assert len(users) >= 2
        user_ids = [u.id for u in users]
        assert admin_user.id in user_ids
        assert vendedor_user.id in user_ids

    def test_list_users_encargado(self, user_service, admin_user, encargado_role, db_session):
        """Test warehouse manager can list users"""
        encargado = User(
            username="encargado",
            email="encargado@test.com",
            password_hash=AuthService.hash_password("EncargadoPass123"),
            role_id=encargado_role.id,
            active_status=True
        )
        db_session.add(encargado)
        db_session.commit()
        db_session.refresh(encargado)

        users = user_service.list_users(encargado)

        assert len(users) >= 1

    def test_list_users_vendedor_denied(self, user_service, vendedor_user):
        """Test vendedor cannot list users"""
        with pytest.raises(InsufficientPermissionsError):
            user_service.list_users(vendedor_user)

    def test_list_users_pagination(self, user_service, admin_user):
        """Test user listing with pagination"""
        users_page1 = user_service.list_users(admin_user, skip=0, limit=1)
        users_page2 = user_service.list_users(admin_user, skip=1, limit=1)

        assert len(users_page1) == 1
        assert len(users_page2) >= 0
        if len(users_page2) == 1:
            assert users_page1[0].id != users_page2[0].id


class TestUpdateUser:
    """Tests for user updates"""

    def test_update_user_username(self, user_service, admin_user, vendedor_user):
        """Test updating user username"""
        updated_user = user_service.update_user(
            user_id=vendedor_user.id,
            updated_by=admin_user,
            username="newusername"
        )

        assert updated_user.username == "newusername"

    def test_update_user_email(self, user_service, admin_user, vendedor_user):
        """Test updating user email"""
        updated_user = user_service.update_user(
            user_id=vendedor_user.id,
            updated_by=admin_user,
            email="newemail@test.com"
        )

        assert updated_user.email == "newemail@test.com"

    def test_update_user_role(self, user_service, admin_user, vendedor_user, encargado_role):
        """Test updating user role"""
        updated_user = user_service.update_user(
            user_id=vendedor_user.id,
            updated_by=admin_user,
            role_id=encargado_role.id
        )

        assert updated_user.role_id == encargado_role.id

    def test_update_user_active_status(self, user_service, admin_user, vendedor_user):
        """Test updating user active status"""
        updated_user = user_service.update_user(
            user_id=vendedor_user.id,
            updated_by=admin_user,
            active_status=False
        )

        assert updated_user.active_status is False

    def test_update_user_permission_denied(self, user_service, vendedor_user, admin_user):
        """Test non-admin cannot update users"""
        with pytest.raises(InsufficientPermissionsError):
            user_service.update_user(
                user_id=admin_user.id,
                updated_by=vendedor_user,
                username="hackername"
            )

    def test_update_user_duplicate_username(self, user_service, admin_user, vendedor_user, db_session, vendedor_role):
        """Test updating to duplicate username"""
        # Create another user
        other_user = User(
            username="otheruser",
            email="other@test.com",
            password_hash=AuthService.hash_password("OtherPass123"),
            role_id=vendedor_role.id,
            active_status=True
        )
        db_session.add(other_user)
        db_session.commit()

        with pytest.raises(UserAlreadyExistsError):
            user_service.update_user(
                user_id=vendedor_user.id,
                updated_by=admin_user,
                username="otheruser"
            )


class TestDeleteUser:
    """Tests for user deletion (soft delete)"""

    def test_delete_user_success(self, user_service, admin_user, vendedor_user, db_session):
        """Test successful user deletion"""
        result = user_service.delete_user(
            user_id=vendedor_user.id,
            deleted_by=admin_user
        )

        assert result is True

        # Verify user is deactivated (soft delete)
        db_session.refresh(vendedor_user)
        assert vendedor_user.active_status is False

    def test_delete_user_permission_denied(self, user_service, vendedor_user, admin_user):
        """Test non-admin cannot delete users"""
        with pytest.raises(InsufficientPermissionsError):
            user_service.delete_user(
                user_id=admin_user.id,
                deleted_by=vendedor_user
            )

    def test_delete_user_not_found(self, user_service, admin_user):
        """Test deleting non-existent user"""
        with pytest.raises(NotFoundError):
            user_service.delete_user(
                user_id=uuid4(),
                deleted_by=admin_user
            )


class TestChangePassword:
    """Tests for password management"""

    def test_change_password_own(self, user_service, vendedor_user, db_session):
        """Test user changing their own password"""
        result = user_service.change_password(
            user_id=vendedor_user.id,
            requester=vendedor_user,
            new_password="NewPassword456",
            old_password="VendedorPass123"
        )

        assert result is True

        # Verify new password works
        db_session.refresh(vendedor_user)
        assert AuthService.verify_password("NewPassword456", vendedor_user.password_hash)

    def test_change_password_wrong_old_password(self, user_service, vendedor_user):
        """Test password change with incorrect old password"""
        with pytest.raises(InvalidCredentialsError) as exc_info:
            user_service.change_password(
                user_id=vendedor_user.id,
                requester=vendedor_user,
                new_password="NewPassword456",
                old_password="WrongPassword"
            )

        assert "incorrect" in str(exc_info.value).lower()

    def test_change_password_admin_override(self, user_service, admin_user, vendedor_user, db_session):
        """Test admin can change password without old password"""
        result = user_service.change_password(
            user_id=vendedor_user.id,
            requester=admin_user,
            new_password="AdminSetPass789",
            old_password=None
        )

        assert result is True

        # Verify new password works
        db_session.refresh(vendedor_user)
        assert AuthService.verify_password("AdminSetPass789", vendedor_user.password_hash)

    def test_change_password_weak_password(self, user_service, vendedor_user):
        """Test password change with weak password"""
        with pytest.raises(WeakPasswordError):
            user_service.change_password(
                user_id=vendedor_user.id,
                requester=vendedor_user,
                new_password="weak",
                old_password="VendedorPass123"
            )

    def test_change_password_other_user_denied(self, user_service, vendedor_user, admin_user):
        """Test vendedor cannot change other user's password"""
        with pytest.raises(InsufficientPermissionsError):
            user_service.change_password(
                user_id=admin_user.id,
                requester=vendedor_user,
                new_password="HackerPass123"
            )


class TestPasswordValidation:
    """Tests for password strength validation"""

    def test_validate_password_too_short(self, user_service):
        """Test password validation rejects short passwords"""
        with pytest.raises(WeakPasswordError) as exc_info:
            user_service._validate_password_strength("Short1")

        assert "8 characters" in str(exc_info.value)

    def test_validate_password_no_uppercase(self, user_service):
        """Test password validation rejects passwords without uppercase"""
        with pytest.raises(WeakPasswordError) as exc_info:
            user_service._validate_password_strength("nouppercase123")

        assert "uppercase" in str(exc_info.value).lower()

    def test_validate_password_no_lowercase(self, user_service):
        """Test password validation rejects passwords without lowercase"""
        with pytest.raises(WeakPasswordError) as exc_info:
            user_service._validate_password_strength("NOLOWERCASE123")

        assert "lowercase" in str(exc_info.value).lower()

    def test_validate_password_no_digit(self, user_service):
        """Test password validation rejects passwords without digits"""
        with pytest.raises(WeakPasswordError) as exc_info:
            user_service._validate_password_strength("NoDigitsHere")

        assert "digit" in str(exc_info.value).lower()

    def test_validate_password_valid(self, user_service):
        """Test password validation accepts strong passwords"""
        # Should not raise exception
        user_service._validate_password_strength("StrongPass123")
        user_service._validate_password_strength("ValidPassword1")
        user_service._validate_password_strength("MySecure99Pass")
