import uuid

import structlog
from sqlalchemy.orm import joinedload

from polar.account.repository import AccountRepository
from polar.enums import AccountType
from polar.exceptions import PolarTaskError
from polar.kit.utils import utc_now
from polar.locker import Locker
from polar.logging import Logger
from polar.models import Account
from polar.worker import (
    AsyncSessionMaker,
    CronTrigger,
    RedisMiddleware,
    TaskPriority,
    actor,
)

from .repository import PayoutRepository
from .service import InsufficientBalance, PayoutAlreadyTriggered
from .service import payout as payout_service

log: Logger = structlog.get_logger()


class PayoutTaskError(PolarTaskError): ...


class PayoutDoesNotExist(PayoutTaskError):
    def __init__(self, payout_id: uuid.UUID) -> None:
        self.payout_id = payout_id
        message = f"The payout with id {payout_id} does not exist."
        super().__init__(message)


class AccountDoesNotExist(PayoutTaskError):
    def __init__(self, account_id: uuid.UUID) -> None:
        self.account_id = account_id
        message = f"The account with id {account_id} does not exist."
        super().__init__(message)


@actor(actor_name="payout.created", priority=TaskPriority.LOW)
async def payout_created(payout_id: uuid.UUID) -> None:
    async with AsyncSessionMaker() as session:
        repository = PayoutRepository(session)
        payout = await repository.get_by_id(
            payout_id, options=repository.get_eager_options()
        )
        if payout is None:
            raise PayoutDoesNotExist(payout_id)

        if payout.processor == AccountType.stripe:
            await payout_service.transfer_stripe(session, payout)


@actor(
    actor_name="payout.trigger_stripe_payouts",
    cron_trigger=CronTrigger(minute=15),
    priority=TaskPriority.LOW,
)
async def trigger_stripe_payouts() -> None:
    async with AsyncSessionMaker() as session:
        await payout_service.trigger_stripe_payouts(session)


@actor(
    actor_name="payout.trigger_scheduled_payouts",
    cron_trigger=CronTrigger(hour=12, minute=0),
    priority=TaskPriority.LOW,
)
async def trigger_scheduled_payouts() -> None:
    async with AsyncSessionMaker() as session:
        await payout_service.trigger_scheduled_payouts(session, utc_now())


@actor(actor_name="payout.create_scheduled", priority=TaskPriority.LOW)
async def create_scheduled_payout(account_id: uuid.UUID) -> None:
    async with AsyncSessionMaker() as session:
        account_repository = AccountRepository.from_session(session)
        account = await account_repository.get_by_id(
            account_id,
            options=(
                joinedload(Account.admin),
                joinedload(Account.users),
                joinedload(Account.organizations),
            ),
        )
        if account is None:
            raise AccountDoesNotExist(account_id)

        locker = Locker(RedisMiddleware.get())
        await payout_service.create_scheduled(session, locker, account=account)


@actor(actor_name="payout.trigger_stripe_payout", priority=TaskPriority.LOW)
async def trigger_payout(
    payout_id: uuid.UUID, account_amount: int | None = None
) -> None:
    async with AsyncSessionMaker() as session:
        repository = PayoutRepository(session)
        payout = await repository.get_by_id(
            payout_id, options=repository.get_eager_options()
        )
        if payout is None:
            raise PayoutDoesNotExist(payout_id)

        try:
            await payout_service.trigger_stripe_payout(session, payout, account_amount)
        except InsufficientBalance:
            # Swallow it, since it's likely the money not having arrived in the Stripe account yet.
            # The payout will be triggered again later.
            pass
        except PayoutAlreadyTriggered:
            # Swallow it, since it's likely a task that's being retried
            # while the payout has already been triggered.
            pass


@actor(actor_name="payout.invoice", priority=TaskPriority.LOW)
async def order_invoice(payout_id: uuid.UUID) -> None:
    async with AsyncSessionMaker() as session:
        repository = PayoutRepository(session)
        payout = await repository.get_by_id(
            payout_id, options=repository.get_eager_options()
        )
        if payout is None:
            raise PayoutDoesNotExist(payout_id)

        await payout_service.generate_invoice(session, payout)
