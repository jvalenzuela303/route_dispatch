"""
Cut-off time service for delivery date calculation

Implements business rules BR-001, BR-002, BR-003 for calculating delivery dates
based on order creation time and Chilean business day rules.

CRITICAL: All timestamps must use America/Santiago timezone
"""

from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
from typing import Optional

from app.models.models import User
from app.exceptions import ValidationError, AdminOverrideRequiredError


class BusinessDayService:
    """Helper service for Chilean business day calculations"""

    # Chilean holidays 2026 (update annually)
    CHILEAN_HOLIDAYS_2026 = {
        date(2026, 1, 1),   # Año Nuevo
        date(2026, 4, 3),   # Viernes Santo
        date(2026, 4, 4),   # Sábado Santo
        date(2026, 5, 1),   # Día del Trabajo
        date(2026, 5, 21),  # Glorias Navales
        date(2026, 6, 29),  # San Pedro y San Pablo
        date(2026, 7, 16),  # Día de la Virgen del Carmen
        date(2026, 8, 15),  # Asunción de la Virgen
        date(2026, 9, 18),  # Día de la Independencia
        date(2026, 9, 19),  # Día de las Glorias del Ejército
        date(2026, 10, 12), # Día del Encuentro de Dos Mundos
        date(2026, 10, 31), # Día de las Iglesias Evangélicas y Protestantes
        date(2026, 11, 1),  # Día de Todos los Santos
        date(2026, 12, 8),  # Inmaculada Concepción
        date(2026, 12, 25), # Navidad
    }

    @staticmethod
    def is_business_day(check_date: date) -> bool:
        """
        Check if date is a business day (Monday-Friday, not holiday)

        Args:
            check_date: Date to check

        Returns:
            bool: True if business day, False otherwise
        """
        # Saturday = 5, Sunday = 6
        if check_date.weekday() in [5, 6]:
            return False

        if check_date in BusinessDayService.CHILEAN_HOLIDAYS_2026:
            return False

        return True

    @staticmethod
    def next_business_day(from_date: date) -> date:
        """
        Get next business day after given date

        Args:
            from_date: Starting date

        Returns:
            date: Next business day
        """
        next_date = from_date + timedelta(days=1)

        while not BusinessDayService.is_business_day(next_date):
            next_date = next_date + timedelta(days=1)

        return next_date

    @staticmethod
    def is_holiday(check_date: date) -> bool:
        """
        Check if date is a Chilean holiday

        Args:
            check_date: Date to check

        Returns:
            bool: True if holiday, False otherwise
        """
        return check_date in BusinessDayService.CHILEAN_HOLIDAYS_2026


class CutoffService:
    """
    Service for calculating delivery dates based on cut-off time rules

    Business Rules:
    - BR-001: Orders <= 12:00:00 → same day (if business day)
    - BR-002: Orders > 15:00:00 → next business day
    - BR-003: Orders 12:00:01 - 15:00:00 → same day (flexible window)
    - BR-017: Admin can override with reason
    """

    TIMEZONE = ZoneInfo("America/Santiago")
    CUTOFF_AM = time(12, 0, 0)   # 12:00:00 (noon)
    CUTOFF_PM = time(15, 0, 0)   # 15:00:00 (3:00 PM)

    @staticmethod
    def calculate_delivery_date(
        order_created_at: datetime,
        user: Optional[User] = None,
        override_date: Optional[date] = None,
        override_reason: Optional[str] = None
    ) -> date:
        """
        Calculate delivery date based on cut-off rules

        Args:
            order_created_at: Order creation timestamp (must be in America/Santiago)
            user: User creating the order (required for override)
            override_date: Optional override date (Admin only)
            override_reason: Required if override_date provided

        Returns:
            date: Calculated delivery date

        Raises:
            ValidationError: If timezone incorrect or override_reason missing
            AdminOverrideRequiredError: If override attempted by non-Admin
        """
        # Ensure correct timezone
        if order_created_at.tzinfo != CutoffService.TIMEZONE:
            order_created_at = order_created_at.astimezone(CutoffService.TIMEZONE)

        created_time = order_created_at.time()
        created_date = order_created_at.date()

        # Calculate default delivery date (without override)
        calculated_date = CutoffService._calculate_default_delivery_date(
            created_time, created_date
        )

        # Handle Admin override (BR-017)
        if override_date is not None:
            return CutoffService._handle_override(
                user=user,
                created_time=created_time,
                calculated_date=calculated_date,
                override_date=override_date,
                override_reason=override_reason
            )

        return calculated_date

    @staticmethod
    def validate_delivery_date_override(
        order,
        requested_delivery_date: date,
        user: User
    ) -> bool:
        """
        Validate if user can override delivery_date

        Only Administrador can override (BR-002)

        Args:
            order: Order instance
            requested_delivery_date: Requested delivery date
            user: User attempting override

        Returns:
            bool: True if override permitted

        Raises:
            AdminOverrideRequiredError: If user not Administrador
        """
        if user.role.role_name != 'Administrador':
            raise AdminOverrideRequiredError('override_delivery_date')

        return True

    @staticmethod
    def is_business_day(check_date: date) -> bool:
        """
        Wrapper for BusinessDayService.is_business_day

        Args:
            check_date: Date to check

        Returns:
            bool: True if business day
        """
        return BusinessDayService.is_business_day(check_date)

    @staticmethod
    def get_next_business_day(from_date: date) -> date:
        """
        Wrapper for BusinessDayService.next_business_day

        Args:
            from_date: Starting date

        Returns:
            date: Next business day
        """
        return BusinessDayService.next_business_day(from_date)

    @staticmethod
    def _calculate_default_delivery_date(created_time: time, created_date: date) -> date:
        """
        Calculate delivery date without overrides

        Args:
            created_time: Time when order was created
            created_date: Date when order was created

        Returns:
            date: Calculated delivery date
        """
        # BR-002: After 3:00 PM → next business day
        if created_time > CutoffService.CUTOFF_PM:
            return BusinessDayService.next_business_day(created_date)

        # BR-001 & BR-003: Before/at 3:00 PM → same day if business day
        if BusinessDayService.is_business_day(created_date):
            return created_date
        else:
            return BusinessDayService.next_business_day(created_date)

    @staticmethod
    def _handle_override(
        user: Optional[User],
        created_time: time,
        calculated_date: date,
        override_date: date,
        override_reason: Optional[str]
    ) -> date:
        """
        Handle admin override logic

        Args:
            user: User attempting override
            created_time: Time when order was created
            calculated_date: Calculated delivery date
            override_date: Requested override date
            override_reason: Reason for override

        Returns:
            date: Override date if valid

        Raises:
            AdminOverrideRequiredError: If user not Administrador
            ValidationError: If override_reason missing or date invalid
        """
        # Permission check
        if not user or user.role.role_name != 'Administrador':
            raise AdminOverrideRequiredError('override_cutoff_time')

        # Reason validation
        if not override_reason or override_reason.strip() == '':
            raise ValidationError(
                code='OVERRIDE_REASON_REQUIRED',
                message='Must provide justification for overriding cutoff rules'
            )

        # Validate override date is business day
        if not BusinessDayService.is_business_day(override_date):
            raise ValidationError(
                code='INVALID_DELIVERY_DATE',
                message=f'Override date {override_date} is not a business day',
                details={'override_date': str(override_date)}
            )

        # Validate not in past
        if override_date < date.today():
            raise ValidationError(
                code='INVALID_DELIVERY_DATE',
                message=f'Override date {override_date} is in the past',
                details={'override_date': str(override_date)}
            )

        # Note: Audit logging will be handled by AuditService in the calling service
        return override_date

    @staticmethod
    def _get_business_rule(created_time: time) -> str:
        """
        Get business rule code based on time

        Args:
            created_time: Time when order was created

        Returns:
            str: Business rule code (BR-001, BR-002, or BR-003)
        """
        if created_time <= CutoffService.CUTOFF_AM:
            return 'BR-001'
        elif created_time > CutoffService.CUTOFF_PM:
            return 'BR-002'
        else:
            return 'BR-003'
