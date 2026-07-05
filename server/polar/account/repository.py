import calendar
import uuid
from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, and_, false, or_

from polar.auth.models import AuthSubject, User, is_organization, is_user
from polar.kit.repository import (
    Options,
    RepositoryBase,
    RepositorySoftDeletionIDMixin,
    RepositorySoftDeletionMixin,
)
from polar.models import Account, Organization
from polar.models.account import PayoutSchedule


class AccountRepository(
    RepositorySoftDeletionIDMixin[Account, UUID],
    RepositorySoftDeletionMixin[Account],
    RepositoryBase[Account],
):
    model = Account

    async def get_by_stripe_id(
        self,
        stripe_id: str,
        *,
        options: Options = (),
        include_deleted: bool = False,
    ) -> Account | None:
        statement = (
            self.get_base_statement(include_deleted=include_deleted)
            .where(Account.stripe_id == stripe_id)
            .options(*options)
        )
        return await self.get_one_or_none(statement)

    async def get_by_user(
        self, user: uuid.UUID, *, options: Options = (), include_deleted: bool = False
    ) -> Account | None:
        statement = (
            self.get_base_statement(include_deleted=include_deleted)
            .join(User, onclause=User.account_id == Account.id)
            .where(User.id == user)
            .options(*options)
        )
        return await self.get_one_or_none(statement)

    async def get_by_organization(
        self,
        organization: uuid.UUID,
        *,
        options: Options = (),
        include_deleted: bool = False,
    ) -> Account | None:
        statement = (
            self.get_base_statement(include_deleted=include_deleted)
            .join(Organization, onclause=Organization.account_id == Account.id)
            .where(Organization.id == organization)
            .options(*options)
        )
        return await self.get_one_or_none(statement)

    async def get_scheduled_payout_accounts(
        self, when: datetime, *, options: Options = ()
    ) -> Sequence[Account]:
        """Return active accounts whose payout schedule is due on `when`.

        Weekly schedules match on the weekday. Monthly schedules match on the
        configured day of the month, and also on the last day of the month when
        the configured day is greater than the month's length (so a day of `31`
        is always paid out on the last day, whatever the month).
        """
        weekday = when.weekday()
        day = when.day
        days_in_month = calendar.monthrange(when.year, when.month)[1]
        is_last_day = day == days_in_month

        weekly_condition = and_(
            Account.payout_schedule == PayoutSchedule.weekly,
            Account.payout_schedule_weekday == weekday,
        )

        monthly_day_condition = Account.payout_schedule_day_of_month == day
        if is_last_day:
            monthly_day_condition = or_(
                monthly_day_condition,
                Account.payout_schedule_day_of_month > day,
            )
        monthly_condition = and_(
            Account.payout_schedule == PayoutSchedule.monthly,
            monthly_day_condition,
        )

        statement = (
            self.get_base_statement()
            .where(Account.status == Account.Status.ACTIVE)
            .where(or_(weekly_condition, monthly_condition))
            .options(*options)
        )
        return await self.get_all(statement)

    def get_readable_statement(
        self, auth_subject: AuthSubject[User | Organization]
    ) -> Select[tuple[Account]]:
        statement = self.get_base_statement()

        if is_user(auth_subject):
            user = auth_subject.subject
            statement = statement.where(Account.admin_id == user.id)
        elif is_organization(auth_subject):
            # Only the admin of the account can access it
            statement = statement.where(false())

        return statement
