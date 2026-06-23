import uuid

import pytest
from pytest_mock import MockerFixture

from polar.benefit.grant.service import benefit_grant as benefit_grant_service
from polar.customer_meter.repository import CustomerMeterRepository
from polar.models import Benefit, Customer, Organization, Subscription
from polar.models.benefit import BenefitType
from polar.enums import SubscriptionRecurringInterval
from polar.postgres import AsyncSession
from polar.redis import Redis
from tests.fixtures.database import SaveFixture
from tests.fixtures.random_objects import (
    create_benefit,
    create_meter,
    create_product,
    create_subscription,
    set_product_benefits,
)


@pytest.mark.asyncio
class TestMeterCreditBenefitIntegration:
    """
    Integration tests for meter credit benefits.

    These tests verify the end-to-end flow of granting meter credit benefits
    and ensuring CustomerMeter records are created correctly.
    """

    async def test_grant_creates_customer_meter(
        self,
        session: AsyncSession,
        redis: Redis,
        save_fixture: SaveFixture,
        customer: Customer,
        organization: Organization,
        subscription: Subscription,
    ) -> None:
        """
        Test that granting a meter credit benefit creates a CustomerMeter immediately.

        This verifies that active_meters will include the meter right after
        subscribing to a product with a meter credit benefit.
        """
        # Create a meter for the organization
        meter = await create_meter(save_fixture, organization=organization)

        # Create a meter credit benefit
        benefit = await create_benefit(
            save_fixture,
            organization=organization,
            type=BenefitType.meter_credit,
            properties={
                "meter_id": str(meter.id),
                "units": 100,
                "rollover": False,
            },
        )

        # Grant the benefit to the customer
        grant = await benefit_grant_service.grant_benefit(
            session, redis, customer, benefit, subscription=subscription
        )

        # Verify the grant was created
        assert grant is not None
        assert grant.is_granted
        assert grant.customer_id == customer.id
        assert grant.benefit_id == benefit.id

        # Verify a CustomerMeter was created
        customer_meter_repo = CustomerMeterRepository.from_session(session)
        customer_meter = await customer_meter_repo.get_by_customer_and_meter(
            customer.id, meter.id
        )

        assert customer_meter is not None
        assert customer_meter.customer_id == customer.id
        assert customer_meter.meter_id == meter.id
        assert customer_meter.credited_units == 100
        assert customer_meter.consumed_units == 0
        assert customer_meter.balance == 100


async def _create_meter_credit_benefit(
    save_fixture: SaveFixture,
    organization: Organization,
    *,
    meter_id: str,
    units: int = 100,
    per_seat: bool | None = None,
) -> Benefit:
    properties: dict[str, object] = {
        "meter_id": meter_id,
        "units": units,
        "rollover": False,
    }
    if per_seat is not None:
        properties["per_seat"] = per_seat
    return await create_benefit(
        save_fixture,
        organization=organization,
        type=BenefitType.meter_credit,
        properties=properties,
    )


@pytest.mark.asyncio
class TestEnqueueBenefitsGrantsRouting:
    """
    Verify which benefits `enqueue_benefits_grants` enqueues depending on the
    `per_seat` property, the product type, and whether a member_id is passed.
    """

    async def test_seat_based_whole_credit_for_subscription_scope(
        self,
        mocker: MockerFixture,
        session: AsyncSession,
        save_fixture: SaveFixture,
        organization: Organization,
        customer: Customer,
    ) -> None:
        """
        Seat-based product, member_id=None: only whole-subscription benefits
        (per_seat=False) are enqueued; per-seat benefits are skipped (they're
        handled per seat).
        """
        enqueue_job_mock = mocker.patch("polar.benefit.grant.service.enqueue_job")
        meter = await create_meter(save_fixture, organization=organization)
        whole_benefit = await _create_meter_credit_benefit(
            save_fixture, organization, meter_id=str(meter.id), per_seat=False
        )
        per_seat_benefit = await _create_meter_credit_benefit(
            save_fixture, organization, meter_id=str(meter.id), per_seat=True
        )
        product = await create_product(
            save_fixture,
            organization=organization,
            recurring_interval=SubscriptionRecurringInterval.month,
            prices=[("seat", 1000, "usd")],
        )
        product = await set_product_benefits(
            save_fixture,
            product=product,
            benefits=[whole_benefit, per_seat_benefit],
        )
        subscription = await create_subscription(
            save_fixture, product=product, customer=customer, seats=5
        )

        await benefit_grant_service.enqueue_benefits_grants(
            session,
            "grant",
            customer,
            product,
            member_id=None,
            subscription=subscription,
        )

        enqueue_job_mock.assert_called_once()
        grant_benefit_ids = enqueue_job_mock.call_args[1]["grant_benefit_ids"]
        assert set(grant_benefit_ids) == {whole_benefit.id}

    async def test_seat_based_per_seat_credit_for_member_scope(
        self,
        mocker: MockerFixture,
        session: AsyncSession,
        save_fixture: SaveFixture,
        organization: Organization,
        customer: Customer,
    ) -> None:
        """
        Seat-based product, member_id provided (seat flow): only per-seat
        benefits are enqueued; whole-subscription benefits are skipped.
        """
        enqueue_job_mock = mocker.patch("polar.benefit.grant.service.enqueue_job")
        # No member exists for this id; the service only needs the routing to
        # produce the right benefit ids (existing_grants is empty).
        member_id = uuid.uuid4()
        meter = await create_meter(save_fixture, organization=organization)
        whole_benefit = await _create_meter_credit_benefit(
            save_fixture, organization, meter_id=str(meter.id), per_seat=False
        )
        per_seat_benefit = await _create_meter_credit_benefit(
            save_fixture, organization, meter_id=str(meter.id), per_seat=True
        )
        product = await create_product(
            save_fixture,
            organization=organization,
            recurring_interval=SubscriptionRecurringInterval.month,
            prices=[("seat", 1000, "usd")],
        )
        product = await set_product_benefits(
            save_fixture,
            product=product,
            benefits=[whole_benefit, per_seat_benefit],
        )
        subscription = await create_subscription(
            save_fixture, product=product, customer=customer, seats=5
        )

        await benefit_grant_service.enqueue_benefits_grants(
            session,
            "grant",
            customer,
            product,
            member_id=member_id,
            subscription=subscription,
        )

        enqueue_job_mock.assert_called_once()
        grant_benefit_ids = enqueue_job_mock.call_args[1]["grant_benefit_ids"]
        assert set(grant_benefit_ids) == {per_seat_benefit.id}

    async def test_non_seat_product_all_benefits(
        self,
        mocker: MockerFixture,
        session: AsyncSession,
        save_fixture: SaveFixture,
        organization: Organization,
        customer: Customer,
    ) -> None:
        """
        Non-seat product, member_id=None: all benefits are enqueued, regardless
        of per_seat (unchanged behavior).
        """
        enqueue_job_mock = mocker.patch("polar.benefit.grant.service.enqueue_job")
        meter = await create_meter(save_fixture, organization=organization)
        benefit_whole = await _create_meter_credit_benefit(
            save_fixture, organization, meter_id=str(meter.id), per_seat=False
        )
        benefit_per_seat = await _create_meter_credit_benefit(
            save_fixture, organization, meter_id=str(meter.id), per_seat=True
        )
        product = await create_product(
            save_fixture,
            organization=organization,
            recurring_interval=SubscriptionRecurringInterval.month,
            prices=[(1000, "usd")],
        )
        product = await set_product_benefits(
            save_fixture,
            product=product,
            benefits=[benefit_whole, benefit_per_seat],
        )
        subscription = await create_subscription(
            save_fixture, product=product, customer=customer
        )

        await benefit_grant_service.enqueue_benefits_grants(
            session,
            "grant",
            customer,
            product,
            member_id=None,
            subscription=subscription,
        )

        enqueue_job_mock.assert_called_once()
        grant_benefit_ids = enqueue_job_mock.call_args[1]["grant_benefit_ids"]
        assert set(grant_benefit_ids) == {benefit_whole.id, benefit_per_seat.id}

    async def test_backward_compat_no_per_seat_key_treated_as_per_seat(
        self,
        mocker: MockerFixture,
        session: AsyncSession,
        save_fixture: SaveFixture,
        organization: Organization,
        customer: Customer,
    ) -> None:
        """
        Seat-based product, member_id=None: a benefit whose properties lack the
        per_seat key behaves as per_seat=True, so it is NOT enqueued at the
        subscription scope (it's handled per seat).
        """
        enqueue_job_mock = mocker.patch("polar.benefit.grant.service.enqueue_job")
        meter = await create_meter(save_fixture, organization=organization)
        legacy_benefit = await _create_meter_credit_benefit(
            save_fixture, organization, meter_id=str(meter.id), per_seat=None
        )
        product = await create_product(
            save_fixture,
            organization=organization,
            recurring_interval=SubscriptionRecurringInterval.month,
            prices=[("seat", 1000, "usd")],
        )
        product = await set_product_benefits(
            save_fixture, product=product, benefits=[legacy_benefit]
        )
        subscription = await create_subscription(
            save_fixture, product=product, customer=customer, seats=3
        )

        await benefit_grant_service.enqueue_benefits_grants(
            session,
            "grant",
            customer,
            product,
            member_id=None,
            subscription=subscription,
        )

        # Nothing eligible for the subscription scope -> no job enqueued.
        enqueue_job_mock.assert_not_called()


@pytest.mark.asyncio
class TestWholeCreditTotalUnits:
    """
    End-to-end credited total for the whole-credit case: a single grant credits
    exactly `units` regardless of the seat count.
    """

    async def test_whole_credit_grants_units_once(
        self,
        session: AsyncSession,
        redis: Redis,
        save_fixture: SaveFixture,
        organization: Organization,
        customer: Customer,
    ) -> None:
        meter = await create_meter(save_fixture, organization=organization)
        benefit = await _create_meter_credit_benefit(
            save_fixture,
            organization,
            meter_id=str(meter.id),
            units=100,
            per_seat=False,
        )
        product = await create_product(
            save_fixture,
            organization=organization,
            recurring_interval=SubscriptionRecurringInterval.month,
            prices=[("seat", 1000, "usd")],
        )
        product = await set_product_benefits(
            save_fixture, product=product, benefits=[benefit]
        )
        subscription = await create_subscription(
            save_fixture, product=product, customer=customer, seats=5
        )

        # Whole credit: granted once for the subscription (member=None).
        grant = await benefit_grant_service.grant_benefit(
            session, redis, customer, benefit, subscription=subscription
        )
        assert grant.is_granted

        customer_meter_repo = CustomerMeterRepository.from_session(session)
        customer_meter = await customer_meter_repo.get_by_customer_and_meter(
            customer.id, meter.id
        )
        assert customer_meter is not None
        # Exactly `units`, not units * seats.
        assert customer_meter.credited_units == 100
        assert customer_meter.balance == 100
