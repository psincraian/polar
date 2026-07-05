import datetime

import pytest

from polar.account.repository import AccountRepository
from polar.models import Account
from polar.models.account import PayoutSchedule
from polar.postgres import AsyncSession
from tests.fixtures.database import SaveFixture
from tests.fixtures.random_objects import (
    create_account,
    create_organization,
    create_user,
)


async def _create_scheduled_account(
    save_fixture: SaveFixture, **schedule_kwargs: object
) -> Account:
    organization = await create_organization(save_fixture)
    user = await create_user(save_fixture)
    account = await create_account(save_fixture, organization, user)
    for key, value in schedule_kwargs.items():
        setattr(account, key, value)
    await save_fixture(account)
    return account


@pytest.mark.asyncio
class TestGetScheduledPayoutAccounts:
    async def test_returns_due_weekly_and_monthly_accounts(
        self, save_fixture: SaveFixture, session: AsyncSession
    ) -> None:
        weekly = await _create_scheduled_account(
            save_fixture,
            payout_schedule=PayoutSchedule.weekly,
            payout_schedule_weekday=0,
        )
        monthly = await _create_scheduled_account(
            save_fixture,
            payout_schedule=PayoutSchedule.monthly,
            payout_schedule_day_of_month=3,
        )
        other_weekday = await _create_scheduled_account(
            save_fixture,
            payout_schedule=PayoutSchedule.weekly,
            payout_schedule_weekday=4,
        )
        manual = await _create_scheduled_account(
            save_fixture, payout_schedule=PayoutSchedule.manual
        )

        repository = AccountRepository.from_session(session)
        # 2025-02-03 is a Monday (weekday 0) and the 3rd of the month
        accounts = await repository.get_scheduled_payout_accounts(
            datetime.datetime(2025, 2, 3)
        )
        account_ids = {account.id for account in accounts}

        assert weekly.id in account_ids
        assert monthly.id in account_ids
        assert other_weekday.id not in account_ids
        assert manual.id not in account_ids

    async def test_monthly_day_31_matches_last_day_of_shorter_month(
        self, save_fixture: SaveFixture, session: AsyncSession
    ) -> None:
        monthly = await _create_scheduled_account(
            save_fixture,
            payout_schedule=PayoutSchedule.monthly,
            payout_schedule_day_of_month=31,
        )

        repository = AccountRepository.from_session(session)

        # February 28th is the last day, so a day-31 schedule is due
        due = await repository.get_scheduled_payout_accounts(
            datetime.datetime(2025, 2, 28)
        )
        assert monthly.id in {account.id for account in due}

        # The 27th is not the last day, so it's not due
        not_due = await repository.get_scheduled_payout_accounts(
            datetime.datetime(2025, 2, 27)
        )
        assert monthly.id not in {account.id for account in not_due}

    async def test_excludes_non_active_accounts(
        self, save_fixture: SaveFixture, session: AsyncSession
    ) -> None:
        inactive = await _create_scheduled_account(
            save_fixture,
            payout_schedule=PayoutSchedule.weekly,
            payout_schedule_weekday=0,
            status=Account.Status.UNDER_REVIEW,
        )

        repository = AccountRepository.from_session(session)
        accounts = await repository.get_scheduled_payout_accounts(
            datetime.datetime(2025, 2, 3)
        )

        assert inactive.id not in {account.id for account in accounts}
