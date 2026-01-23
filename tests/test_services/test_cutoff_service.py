"""
Unit tests for CutoffService

Tests business rules BR-001, BR-002, BR-003, BR-017
"""

import pytest
from datetime import datetime, date, time
from zoneinfo import ZoneInfo

from app.services.cutoff_service import CutoffService, BusinessDayService
from app.exceptions import ValidationError, AdminOverrideRequiredError


class TestBusinessDayService:
    """Test suite for business day calculations"""

    def test_is_business_day_monday(self):
        """Monday should be business day"""
        monday = date(2026, 1, 19)  # Monday
        assert BusinessDayService.is_business_day(monday) is True

    def test_is_business_day_friday(self):
        """Friday should be business day"""
        friday = date(2026, 1, 23)  # Friday
        assert BusinessDayService.is_business_day(friday) is True

    def test_is_business_day_saturday(self):
        """Saturday should not be business day"""
        saturday = date(2026, 1, 24)  # Saturday
        assert BusinessDayService.is_business_day(saturday) is False

    def test_is_business_day_sunday(self):
        """Sunday should not be business day"""
        sunday = date(2026, 1, 25)  # Sunday
        assert BusinessDayService.is_business_day(sunday) is False

    def test_is_business_day_new_year(self):
        """January 1st should not be business day (holiday)"""
        new_year = date(2026, 1, 1)  # Año Nuevo
        assert BusinessDayService.is_business_day(new_year) is False

    def test_is_business_day_independence_day(self):
        """September 18th should not be business day (Chilean holiday)"""
        independence_day = date(2026, 9, 18)  # Independencia
        assert BusinessDayService.is_business_day(independence_day) is False

    def test_next_business_day_thursday_to_friday(self):
        """Next business day from Thursday should be Friday"""
        thursday = date(2026, 1, 22)
        next_bd = BusinessDayService.next_business_day(thursday)
        assert next_bd == date(2026, 1, 23)

    def test_next_business_day_friday_to_monday(self):
        """Next business day from Friday should be Monday"""
        friday = date(2026, 1, 23)
        next_bd = BusinessDayService.next_business_day(friday)
        assert next_bd == date(2026, 1, 26)

    def test_next_business_day_skip_weekend(self):
        """Should skip entire weekend"""
        saturday = date(2026, 1, 24)
        next_bd = BusinessDayService.next_business_day(saturday)
        assert next_bd == date(2026, 1, 26)  # Monday

    def test_next_business_day_skip_holiday(self):
        """Should skip Chilean holiday (Independence Day weekend)"""
        # Thursday before Independence Day (Friday 18th)
        thursday = date(2026, 9, 17)
        next_bd = BusinessDayService.next_business_day(thursday)
        # Should skip Friday 18 (holiday), Saturday 19 (holiday), Sunday 20, Monday 21
        assert next_bd == date(2026, 9, 21)


class TestCutoffServiceCalculations:
    """Test suite for cut-off time delivery date calculations"""

    CHILE_TZ = ZoneInfo("America/Santiago")

    def test_cutoff_am_boundary_exactly_noon(self, mock_admin_user):
        """BR-001: Order at exactly 12:00:00 should be same day"""
        # Wednesday 2026-01-21 at 12:00:00
        created_at = datetime(2026, 1, 21, 12, 0, 0, tzinfo=self.CHILE_TZ)

        delivery_date = CutoffService.calculate_delivery_date(
            order_created_at=created_at,
            user=mock_admin_user
        )

        assert delivery_date == date(2026, 1, 21)  # Same day

    def test_cutoff_am_one_second_after_noon(self, mock_admin_user):
        """BR-003: Order at 12:00:01 should be same day (intermediate window)"""
        created_at = datetime(2026, 1, 21, 12, 0, 1, tzinfo=self.CHILE_TZ)

        delivery_date = CutoffService.calculate_delivery_date(
            order_created_at=created_at,
            user=mock_admin_user
        )

        assert delivery_date == date(2026, 1, 21)  # Same day

    def test_cutoff_am_before_noon(self, mock_admin_user):
        """BR-001: Order at 11:59:59 should be same day"""
        created_at = datetime(2026, 1, 21, 11, 59, 59, tzinfo=self.CHILE_TZ)

        delivery_date = CutoffService.calculate_delivery_date(
            order_created_at=created_at,
            user=mock_admin_user
        )

        assert delivery_date == date(2026, 1, 21)  # Same day

    def test_cutoff_pm_boundary_exactly_3pm(self, mock_admin_user):
        """BR-003: Order at exactly 15:00:00 should be same day"""
        created_at = datetime(2026, 1, 21, 15, 0, 0, tzinfo=self.CHILE_TZ)

        delivery_date = CutoffService.calculate_delivery_date(
            order_created_at=created_at,
            user=mock_admin_user
        )

        assert delivery_date == date(2026, 1, 21)  # Same day

    def test_cutoff_pm_one_second_after_3pm(self, mock_admin_user):
        """BR-002: Order at 15:00:01 should be next business day"""
        created_at = datetime(2026, 1, 21, 15, 0, 1, tzinfo=self.CHILE_TZ)

        delivery_date = CutoffService.calculate_delivery_date(
            order_created_at=created_at,
            user=mock_admin_user
        )

        # 2026-01-21 is Wednesday, next business day is Thursday
        assert delivery_date == date(2026, 1, 22)

    def test_cutoff_friday_after_3pm(self, mock_admin_user):
        """BR-002: Friday after 3 PM should be next Monday"""
        # Friday 2026-01-23 at 16:00
        created_at = datetime(2026, 1, 23, 16, 0, 0, tzinfo=self.CHILE_TZ)

        delivery_date = CutoffService.calculate_delivery_date(
            order_created_at=created_at,
            user=mock_admin_user
        )

        # Next business day is Monday
        assert delivery_date == date(2026, 1, 26)

    def test_cutoff_saturday_morning(self, mock_admin_user):
        """BR-001: Saturday should always be next Monday (not business day)"""
        # Saturday 2026-01-24 at 10:00 AM
        created_at = datetime(2026, 1, 24, 10, 0, 0, tzinfo=self.CHILE_TZ)

        delivery_date = CutoffService.calculate_delivery_date(
            order_created_at=created_at,
            user=mock_admin_user
        )

        # Next business day is Monday
        assert delivery_date == date(2026, 1, 26)

    def test_cutoff_sunday_morning(self, mock_admin_user):
        """BR-001: Sunday should always be next Monday"""
        # Sunday 2026-01-25 at 10:00 AM
        created_at = datetime(2026, 1, 25, 10, 0, 0, tzinfo=self.CHILE_TZ)

        delivery_date = CutoffService.calculate_delivery_date(
            order_created_at=created_at,
            user=mock_admin_user
        )

        # Next business day is Monday
        assert delivery_date == date(2026, 1, 26)

    def test_cutoff_holiday_morning(self, mock_admin_user):
        """BR-001: Holiday should be next business day"""
        # Independence Day (Friday) at 10:00 AM
        created_at = datetime(2026, 9, 18, 10, 0, 0, tzinfo=self.CHILE_TZ)

        delivery_date = CutoffService.calculate_delivery_date(
            order_created_at=created_at,
            user=mock_admin_user
        )

        # Next business day is Monday (skip 19th holiday and weekend)
        assert delivery_date == date(2026, 9, 21)


class TestCutoffServiceOverrides:
    """Test suite for admin override functionality"""

    CHILE_TZ = ZoneInfo("America/Santiago")

    def test_admin_override_with_reason(self, mock_admin_user):
        """BR-017: Admin can override cutoff with reason"""
        # Friday 16:00 (should be Monday, but override to Friday)
        created_at = datetime(2026, 1, 23, 16, 0, 0, tzinfo=self.CHILE_TZ)

        delivery_date = CutoffService.calculate_delivery_date(
            order_created_at=created_at,
            user=mock_admin_user,
            override_date=date(2026, 1, 23),  # Same day override
            override_reason="Cliente VIP - Emergencia"
        )

        assert delivery_date == date(2026, 1, 23)

    def test_vendedor_override_denied(self, mock_vendedor_user):
        """BR-017: Vendedor cannot override cutoff"""
        created_at = datetime(2026, 1, 23, 16, 0, 0, tzinfo=self.CHILE_TZ)

        with pytest.raises(AdminOverrideRequiredError) as exc_info:
            CutoffService.calculate_delivery_date(
                order_created_at=created_at,
                user=mock_vendedor_user,
                override_date=date(2026, 1, 23),
                override_reason="Intento de override"
            )

        assert exc_info.value.code == 'ADMIN_OVERRIDE_REQUIRED'

    def test_override_without_reason(self, mock_admin_user):
        """BR-017: Override requires reason"""
        created_at = datetime(2026, 1, 23, 16, 0, 0, tzinfo=self.CHILE_TZ)

        with pytest.raises(ValidationError) as exc_info:
            CutoffService.calculate_delivery_date(
                order_created_at=created_at,
                user=mock_admin_user,
                override_date=date(2026, 1, 23),
                override_reason=""  # Empty reason
            )

        assert exc_info.value.code == 'OVERRIDE_REASON_REQUIRED'

    def test_override_to_non_business_day(self, mock_admin_user):
        """Override to weekend should fail"""
        created_at = datetime(2026, 1, 23, 16, 0, 0, tzinfo=self.CHILE_TZ)

        with pytest.raises(ValidationError) as exc_info:
            CutoffService.calculate_delivery_date(
                order_created_at=created_at,
                user=mock_admin_user,
                override_date=date(2026, 1, 24),  # Saturday
                override_reason="Invalid override"
            )

        assert exc_info.value.code == 'INVALID_DELIVERY_DATE'

    def test_override_to_past_date(self, mock_admin_user):
        """Override to past date should fail"""
        created_at = datetime(2026, 1, 23, 16, 0, 0, tzinfo=self.CHILE_TZ)

        with pytest.raises(ValidationError) as exc_info:
            CutoffService.calculate_delivery_date(
                order_created_at=created_at,
                user=mock_admin_user,
                override_date=date(2026, 1, 1),  # Past date
                override_reason="Invalid override"
            )

        assert exc_info.value.code == 'INVALID_DELIVERY_DATE'
