"""
Vehicle Service for vehicle and fleet management

Handles all vehicle-related operations:
- Vehicle CRUD with soft delete
- Driver assignment validation
- Route assignment and release
- Status management (AVAILABLE, IN_ROUTE, MAINTENANCE)
"""

from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError as SQLIntegrityError

from app.models.models import Vehicle, Route, User
from app.models.enums import VehicleStatus, RouteStatus
from app.schemas.vehicle_schemas import VehicleCreate, VehicleUpdate
from app.exceptions import (
    NotFoundError,
    IntegrityError,
    InsufficientPermissionsError,
    ValidationError,
)


class VehicleService:
    """
    Service for managing fleet vehicles.

    Enforces:
    - Unique plate_number constraint
    - Driver must have role 'Repartidor'
    - Vehicle must be AVAILABLE before assigning to route
    - Soft delete (active=False) instead of hard delete
    """

    def __init__(self, db: Session):
        self.db = db

    # ─────────────────────────────────────────────────────────────────
    # CRUD
    # ─────────────────────────────────────────────────────────────────

    def create_vehicle(self, data: VehicleCreate) -> Vehicle:
        """
        Create a new vehicle.

        Raises:
            IntegrityError: If plate_number already exists
            NotFoundError: If assigned_driver_id doesn't exist or wrong role
        """
        # Check plate uniqueness
        existing = (
            self.db.query(Vehicle)
            .filter(Vehicle.plate_number == data.plate_number)
            .first()
        )
        if existing:
            raise IntegrityError(
                code="VEHICLE_PLATE_EXISTS",
                message=f"Vehicle with plate '{data.plate_number}' already exists",
            )

        # Validate driver if provided
        if data.assigned_driver_id:
            self._validate_driver(data.assigned_driver_id)

        vehicle = Vehicle(
            plate_number=data.plate_number,
            alias=data.alias,
            brand=data.brand,
            model_name=data.model_name,
            year=data.year,
            max_load_kg=data.max_load_kg,
            max_volume_m3=data.max_volume_m3,
            gps_device_id=data.gps_device_id,
            assigned_driver_id=data.assigned_driver_id,
            status=VehicleStatus.AVAILABLE,
            active=True,
        )

        try:
            self.db.add(vehicle)
            self.db.commit()
            self.db.refresh(vehicle)
        except SQLIntegrityError:
            self.db.rollback()
            raise IntegrityError(
                code="VEHICLE_PLATE_EXISTS",
                message=f"Vehicle with plate '{data.plate_number}' already exists",
            )

        return vehicle

    def get_vehicle(self, vehicle_id: UUID) -> Vehicle:
        """
        Get vehicle by ID.

        Raises:
            NotFoundError: If vehicle doesn't exist or is inactive
        """
        vehicle = (
            self.db.query(Vehicle)
            .filter(Vehicle.id == vehicle_id, Vehicle.active == True)
            .first()
        )
        if not vehicle:
            raise NotFoundError(
                code="VEHICLE_NOT_FOUND",
                message=f"Vehicle with ID {vehicle_id} not found",
            )
        return vehicle

    def get_all_vehicles(
        self,
        include_inactive: bool = False,
        status_filter: Optional[VehicleStatus] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[List[Vehicle], int]:
        """
        Return paginated list of vehicles.

        Returns:
            (items, total) tuple
        """
        query = self.db.query(Vehicle)

        if not include_inactive:
            query = query.filter(Vehicle.active == True)

        if status_filter:
            query = query.filter(Vehicle.status == status_filter)

        total = query.count()
        items = query.order_by(Vehicle.plate_number).offset(skip).limit(limit).all()
        return items, total

    def get_available_vehicles(self) -> List[Vehicle]:
        """Return active vehicles with AVAILABLE status."""
        return (
            self.db.query(Vehicle)
            .filter(
                Vehicle.active == True,
                Vehicle.status == VehicleStatus.AVAILABLE,
            )
            .order_by(Vehicle.plate_number)
            .all()
        )

    def update_vehicle(self, vehicle_id: UUID, data: VehicleUpdate) -> Vehicle:
        """
        Update vehicle fields (partial update — only set fields are updated).

        Raises:
            NotFoundError: If vehicle not found
            NotFoundError: If new driver not found or wrong role
        """
        vehicle = self.get_vehicle(vehicle_id)

        update_data = data.model_dump(exclude_unset=True)

        # Validate driver change
        if "assigned_driver_id" in update_data and update_data["assigned_driver_id"]:
            self._validate_driver(update_data["assigned_driver_id"])

        for field, value in update_data.items():
            setattr(vehicle, field, value)

        self.db.commit()
        self.db.refresh(vehicle)
        return vehicle

    def soft_delete(self, vehicle_id: UUID) -> None:
        """
        Soft-delete a vehicle (set active=False).

        Raises:
            NotFoundError: If vehicle not found
            ValidationError: If vehicle is currently IN_ROUTE
        """
        vehicle = self.get_vehicle(vehicle_id)

        if vehicle.status == VehicleStatus.IN_ROUTE:
            raise ValidationError(
                code="VEHICLE_IN_ROUTE",
                message="Cannot delete a vehicle that is currently on a route",
                details={"vehicle_id": str(vehicle_id), "status": vehicle.status},
            )

        vehicle.active = False
        self.db.commit()

    # ─────────────────────────────────────────────────────────────────
    # Driver assignment
    # ─────────────────────────────────────────────────────────────────

    def assign_driver(self, vehicle_id: UUID, user_id: UUID) -> Vehicle:
        """
        Assign a Repartidor driver to a vehicle.

        Raises:
            NotFoundError: Vehicle or user not found
            ValidationError: User is not a Repartidor
        """
        vehicle = self.get_vehicle(vehicle_id)
        self._validate_driver(user_id)

        vehicle.assigned_driver_id = user_id
        self.db.commit()
        self.db.refresh(vehicle)
        return vehicle

    def unassign_driver(self, vehicle_id: UUID) -> Vehicle:
        """Remove driver assignment from vehicle."""
        vehicle = self.get_vehicle(vehicle_id)
        vehicle.assigned_driver_id = None
        self.db.commit()
        self.db.refresh(vehicle)
        return vehicle

    # ─────────────────────────────────────────────────────────────────
    # Route assignment
    # ─────────────────────────────────────────────────────────────────

    def assign_to_route(self, vehicle_id: UUID, route_id: UUID) -> Route:
        """
        Assign vehicle to a route and mark vehicle as IN_ROUTE.

        Raises:
            NotFoundError: Vehicle or route not found
            ValidationError: Vehicle is not AVAILABLE
        """
        vehicle = self.get_vehicle(vehicle_id)

        if vehicle.status != VehicleStatus.AVAILABLE:
            raise ValidationError(
                code="VEHICLE_NOT_AVAILABLE",
                message=f"Vehicle '{vehicle.plate_number}' is not available "
                        f"(current status: {vehicle.status})",
                details={"vehicle_id": str(vehicle_id), "status": vehicle.status},
            )

        route = self.db.query(Route).filter(Route.id == route_id).first()
        if not route:
            raise NotFoundError(
                code="ROUTE_NOT_FOUND",
                message=f"Route with ID {route_id} not found",
            )

        route.vehicle_id = vehicle_id
        vehicle.status = VehicleStatus.IN_ROUTE
        self.db.commit()
        self.db.refresh(route)
        return route

    def release_from_route(self, vehicle_id: UUID) -> Vehicle:
        """
        Release vehicle from route — set status back to AVAILABLE.

        Raises:
            NotFoundError: Vehicle not found
        """
        vehicle = self.get_vehicle(vehicle_id)
        vehicle.status = VehicleStatus.AVAILABLE
        self.db.commit()
        self.db.refresh(vehicle)
        return vehicle

    def set_maintenance(self, vehicle_id: UUID) -> Vehicle:
        """Put vehicle into MAINTENANCE status."""
        vehicle = self.get_vehicle(vehicle_id)

        if vehicle.status == VehicleStatus.IN_ROUTE:
            raise ValidationError(
                code="VEHICLE_IN_ROUTE",
                message="Cannot set maintenance on a vehicle that is currently on a route",
            )

        vehicle.status = VehicleStatus.MAINTENANCE
        self.db.commit()
        self.db.refresh(vehicle)
        return vehicle

    # ─────────────────────────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────────────────────────

    def _validate_driver(self, user_id: UUID) -> User:
        """
        Validate that user exists and has Repartidor role.

        Raises:
            NotFoundError: User not found
            ValidationError: User is not a Repartidor
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise NotFoundError(
                code="USER_NOT_FOUND",
                message=f"User with ID {user_id} not found",
            )

        if user.role.role_name != "Repartidor":
            raise ValidationError(
                code="INVALID_DRIVER_ROLE",
                message=f"User '{user.username}' has role '{user.role.role_name}', "
                        "only 'Repartidor' can be assigned as driver",
                details={"user_id": str(user_id), "role": user.role.role_name},
            )

        return user
