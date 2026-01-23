"""
Boundary testing for cutoff time business rules (BR-001, BR-002, BR-003)

This test suite verifies exact boundary conditions for delivery date calculation.
Critical test cases include timestamps at exact cutoff times (12:00:00, 15:00:00).

Business Rules:
- BR-001: Orders <= 12:00:00 → same day delivery (if business day)
- BR-002: Orders > 15:00:00 → next business day delivery
- BR-003: Orders 12:00:01 - 15:00:00 → same day delivery (if business day)
"""

import pytest
from datetime import datetime, date, time
from zoneinfo import ZoneInfo

from app.services.cutoff_service import CutoffService, BusinessDayService
from app.exceptions import ValidationError, AdminOverrideRequiredError


class TestCutoffBoundaryConditions:
    """Test exact boundary conditions for cutoff times"""

    TIMEZONE = ZoneInfo("America/Santiago")

    def test_cutoff_exactly_at_noon(self):
        """
        CRITICAL: Test order at exactly 12:00:00 (BR-001 boundary)

        Expected: Same day delivery (BR-001 applies)
        """
        # Wednesday, January 22, 2026 at exactly 12:00:00
        order_time = datetime(2026, 1, 22, 12, 0, 0, tzinfo=self.TIMEZONE)

        delivery_date = CutoffService.calculate_delivery_date(order_time)

        assert delivery_date == date(2026, 1, 22)

    def test_cutoff_one_second_before_noon(self):
        """
        Test order at 11:59:59 (before cutoff)

        Expected: Same day delivery (BR-001)
        """
        order_time = datetime(2026, 1, 22, 11, 59, 59, tzinfo=self.TIMEZONE)

        delivery_date = CutoffService.calculate_delivery_date(order_time)

        assert delivery_date == date(2026, 1, 22)

    def test_cutoff_one_second_after_noon(self):
        """
        Test order at 12:00:01 (after noon cutoff)

        Expected: Same day delivery (BR-003 - flexible window)
        """
        order_time = datetime(2026, 1, 22, 12, 0, 1, tzinfo=self.TIMEZONE)

        delivery_date = CutoffService.calculate_delivery_date(order_time)

        assert delivery_date == date(2026, 1, 22)

    def test_cutoff_exactly_at_3pm(self):
        """
        CRITICAL: Test order at exactly 15:00:00 (BR-002 boundary)

        Expected: Same day delivery (15:00:00 is NOT greater than cutoff)
        """
        order_time = datetime(2026, 1, 22, 15, 0, 0, tzinfo=self.TIMEZONE)

        delivery_date = CutoffService.calculate_delivery_date(order_time)

        # BR-002 says "greater than 15:00:00", so exactly 15:00:00 is same day
        assert delivery_date == date(2026, 1, 22)

    def test_cutoff_one_second_before_3pm(self):
        """
        Test order at 14:59:59 (before PM cutoff)

        Expected: Same day delivery (BR-003)
        """
        order_time = datetime(2026, 1, 22, 14, 59, 59, tzinfo=self.TIMEZONE)

        delivery_date = CutoffService.calculate_delivery_date(order_time)

        assert delivery_date == date(2026, 1, 22)

    def test_cutoff_one_second_after_3pm(self):
        """
        CRITICAL: Test order at 15:00:01 (after PM cutoff)

        Expected: Next business day delivery (BR-002)
        """
        order_time = datetime(2026, 1, 22, 15, 0, 1, tzinfo=self.TIMEZONE)

        delivery_date = CutoffService.calculate_delivery_date(order_time)

        # Next business day is Friday, January 23, 2026
        assert delivery_date == date(2026, 1, 23)

    def test_cutoff_late_at_night(self):
        """
        Test order at 23:59:59 (very late)

        Expected: Next business day delivery (BR-002)
        """
        order_time = datetime(2026, 1, 22, 23, 59, 59, tzinfo=self.TIMEZONE)

        delivery_date = CutoffService.calculate_delivery_date(order_time)

        assert delivery_date == date(2026, 1, 23)


class TestWeekendAndHolidayBehavior:
    """Test cutoff behavior on weekends and holidays"""

    TIMEZONE = ZoneInfo("America/Santiago")

    def test_order_on_friday_after_cutoff(self):
        """
        Test order on Friday after 15:00:00

        Expected: Next business day is Monday
        """
        # Friday, January 24, 2026 at 15:00:01
        order_time = datetime(2026, 1, 24, 15, 0, 1, tzinfo=self.TIMEZONE)

        delivery_date = CutoffService.calculate_delivery_date(order_time)

        # Next business day is Monday, January 27, 2026
        assert delivery_date == date(2026, 1, 27)

    def test_order_on_saturday_before_cutoff(self):
        """
        Test order on Saturday (non-business day)

        Expected: Next business day (Monday)
        """
        # Saturday, January 25, 2026 at 10:00:00
        order_time = datetime(2026, 1, 25, 10, 0, 0, tzinfo=self.TIMEZONE)

        delivery_date = CutoffService.calculate_delivery_date(order_time)

        # Next business day is Monday, January 27, 2026
        assert delivery_date == date(2026, 1, 27)

    def test_order_on_sunday_before_cutoff(self):
        """
        Test order on Sunday (non-business day)

        Expected: Next business day (Monday)
        """
        # Sunday, January 26, 2026 at 10:00:00
        order_time = datetime(2026, 1, 26, 10, 0, 0, tzinfo=self.TIMEZONE)

        delivery_date = CutoffService.calculate_delivery_date(order_time)

        # Next business day is Monday, January 27, 2026
        assert delivery_date == date(2026, 1, 27)

    def test_order_on_new_years_day(self):
        """
        Test order on Chilean holiday (Año Nuevo)

        Expected: Next business day
        """
        # January 1, 2026 (holiday) at 10:00:00
        order_time = datetime(2026, 1, 1, 10, 0, 0, tzinfo=self.TIMEZONE)

        delivery_date = CutoffService.calculate_delivery_date(order_time)

        # Next business day is Friday, January 2, 2026
        assert delivery_date == date(2026, 1, 2)

    def test_order_before_holiday_after_cutoff(self):
        """
        Test order on day before holiday, after cutoff

        Expected: Skip holiday, deliver on next business day
        """
        # December 31, 2025 (before Año Nuevo) at 16:00:00
        order_time = datetime(2025, 12, 31, 16, 0, 0, tzinfo=self.TIMEZONE)

        delivery_date = CutoffService.calculate_delivery_date(order_time)

        # January 1 is holiday, so next business day is January 2
        assert delivery_date == date(2026, 1, 2)


class TestAdminOverride:
    """Test admin override functionality (BR-017)"""

    TIMEZONE = ZoneInfo("America/Santiago")

    def test_admin_override_with_valid_reason(self, admin_user):
        """
        Test admin can override cutoff with valid reason

        Expected: Override date accepted
        """
        # Order at 16:00 (after cutoff, normally next day)
        order_time = datetime(2026, 1, 22, 16, 0, 0, tzinfo=self.TIMEZONE)
        override_date = date(2026, 1, 22)  # Force same day

        delivery_date = CutoffService.calculate_delivery_date(
            order_created_at=order_time,
            user=admin_user,
            override_date=override_date,
            override_reason="Cliente VIP - entrega urgente solicitada"
        )

        assert delivery_date == override_date

    def test_admin_override_without_reason_fails(self, admin_user):
        """
        Test admin override without reason is rejected

        Expected: ValidationError
        """
        order_time = datetime(2026, 1, 22, 16, 0, 0, tzinfo=self.TIMEZONE)
        override_date = date(2026, 1, 22)

        with pytest.raises(ValidationError) as exc_info:
            CutoffService.calculate_delivery_date(
                order_created_at=order_time,
                user=admin_user,
                override_date=override_date,
                override_reason=""  # Empty reason
            )

        assert exc_info.value.code == "OVERRIDE_REASON_REQUIRED"

    def test_non_admin_override_attempt_fails(self, vendedor_user):
        """
        SECURITY TEST: Non-admin cannot override cutoff

        Expected: AdminOverrideRequiredError
        """
        order_time = datetime(2026, 1, 22, 16, 0, 0, tzinfo=self.TIMEZONE)
        override_date = date(2026, 1, 22)

        with pytest.raises(AdminOverrideRequiredError) as exc_info:
            CutoffService.calculate_delivery_date(
                order_created_at=order_time,
                user=vendedor_user,
                override_date=override_date,
                override_reason="Trying to override"
            )

        assert "override_cutoff_time" in str(exc_info.value.message).lower()

    def test_admin_override_to_past_date_fails(self, admin_user):
        """
        Test admin cannot override to past date

        Expected: ValidationError
        """
        order_time = datetime(2026, 1, 22, 16, 0, 0, tzinfo=self.TIMEZONE)
        override_date = date(2026, 1, 20)  # Past date

        with pytest.raises(ValidationError) as exc_info:
            CutoffService.calculate_delivery_date(
                order_created_at=order_time,
                user=admin_user,
                override_date=override_date,
                override_reason="Valid reason"
            )

        assert "past" in str(exc_info.value.message).lower()

    def test_admin_override_to_non_business_day_fails(self, admin_user):
        """
        Test admin cannot override to weekend/holiday

        Expected: ValidationError
        """
        order_time = datetime(2026, 1, 22, 16, 0, 0, tzinfo=self.TIMEZONE)
        override_date = date(2026, 1, 25)  # Saturday

        with pytest.raises(ValidationError) as exc_info:
            CutoffService.calculate_delivery_date(
                order_created_at=order_time,
                user=admin_user,
                override_date=override_date,
                override_reason="Valid reason"
            )

        assert "business day" in str(exc_info.value.message).lower()


class TestBusinessDayCalculations:
    """Test business day helper functions"""

    def test_is_business_day_weekday(self):
        """Test Monday-Friday are business days"""
        # Monday through Friday
        assert BusinessDayService.is_business_day(date(2026, 1, 19))  # Monday
        assert BusinessDayService.is_business_day(date(2026, 1, 20))  # Tuesday
        assert BusinessDayService.is_business_day(date(2026, 1, 21))  # Wednesday
        assert BusinessDayService.is_business_day(date(2026, 1, 22))  # Thursday
        assert BusinessDayService.is_business_day(date(2026, 1, 23))  # Friday

    def test_is_business_day_weekend(self):
        """Test Saturday/Sunday are not business days"""
        assert not BusinessDayService.is_business_day(date(2026, 1, 24))  # Saturday
        assert not BusinessDayService.is_business_day(date(2026, 1, 25))  # Sunday

    def test_is_business_day_holiday(self):
        """Test Chilean holidays are not business days"""
        # January 1 - Año Nuevo
        assert not BusinessDayService.is_business_day(date(2026, 1, 1))

        # May 1 - Día del Trabajo
        assert not BusinessDayService.is_business_day(date(2026, 5, 1))

        # September 18 - Independencia
        assert not BusinessDayService.is_business_day(date(2026, 9, 18))

        # December 25 - Navidad
        assert not BusinessDayService.is_business_day(date(2026, 12, 25))

    def test_next_business_day_from_friday(self):
        """Test next business day from Friday is Monday"""
        # Friday, January 23, 2026
        friday = date(2026, 1, 23)
        next_bd = BusinessDayService.next_business_day(friday)

        # Should be Monday, January 26, 2026
        assert next_bd == date(2026, 1, 26)

    def test_next_business_day_from_saturday(self):
        """Test next business day from Saturday is Monday"""
        saturday = date(2026, 1, 24)
        next_bd = BusinessDayService.next_business_day(saturday)

        assert next_bd == date(2026, 1, 26)

    def test_next_business_day_skip_holiday(self):
        """Test next business day skips holidays"""
        # December 31, 2025
        last_day = date(2025, 12, 31)
        next_bd = BusinessDayService.next_business_day(last_day)

        # Should skip January 1 (holiday) and land on January 2
        assert next_bd == date(2026, 1, 2)
