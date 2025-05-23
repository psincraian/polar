from collections.abc import Callable, Coroutine
from datetime import UTC, datetime, timedelta
from unittest.mock import ANY, MagicMock
from uuid import UUID

import pytest
import pytest_asyncio
from pytest_mock import MockerFixture

from polar.config import settings
from polar.kit.crypto import generate_token_hash_pair, get_token_hash
from polar.kit.db.postgres import AsyncSession
from polar.magic_link.service import InvalidMagicLink
from polar.magic_link.service import magic_link as magic_link_service
from polar.models import MagicLink, User
from tests.fixtures.database import SaveFixture

GenerateMagicLinkToken = Callable[
    [str, UUID | None, datetime | None], Coroutine[None, None, tuple[MagicLink, str]]
]


@pytest.fixture(autouse=True)
def enqueue_email_mock(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("polar.magic_link.service.enqueue_email", autospec=True)


@pytest_asyncio.fixture
async def generate_magic_link_token(
    save_fixture: SaveFixture,
) -> GenerateMagicLinkToken:
    async def _generate_magic_link_token(
        user_email: str, user_id: UUID | None, expires_at: datetime | None
    ) -> tuple[MagicLink, str]:
        token, token_hash = generate_token_hash_pair(secret=settings.SECRET)
        magic_link = MagicLink(
            token_hash=token_hash,
            user_email=user_email,
            user_id=user_id,
            expires_at=expires_at,
        )
        await save_fixture(magic_link)

        return magic_link, token

    return _generate_magic_link_token


@pytest.mark.asyncio
async def test_request(session: AsyncSession) -> None:
    magic_link, token = await magic_link_service.request(session, "user@example.com")

    assert magic_link.user_email == "user@example.com"
    assert magic_link.token_hash == get_token_hash(token, secret=settings.SECRET)
    assert magic_link.expires_at is not None


@pytest.mark.asyncio
async def test_authenticate_invalid_token(session: AsyncSession) -> None:
    # then
    session.expunge_all()

    with pytest.raises(InvalidMagicLink):
        await magic_link_service.authenticate(session, "INVALID_TOKEN")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "expires_at",
    [
        datetime(1900, 1, 1, tzinfo=UTC),
        datetime.now(UTC) - timedelta(seconds=1),
        datetime.now(UTC),
    ],
)
async def test_authenticate_expired_token(
    session: AsyncSession,
    expires_at: datetime,
    generate_magic_link_token: GenerateMagicLinkToken,
) -> None:
    # then
    session.expunge_all()

    _, token = await generate_magic_link_token("user@example.com", None, expires_at)
    with pytest.raises(InvalidMagicLink):
        await magic_link_service.authenticate(session, token)


@pytest.mark.asyncio
async def test_send(
    generate_magic_link_token: GenerateMagicLinkToken, enqueue_email_mock: MagicMock
) -> None:
    magic_link, _ = await generate_magic_link_token("user@example.com", None, None)

    await magic_link_service.send(magic_link, "TOKEN", "BASE_URL")

    enqueue_email_mock.assert_called_once_with(
        to_email_addr="user@example.com", html_content=ANY, subject="Sign in to Polar"
    )


@pytest.mark.asyncio
async def test_authenticate_existing_user(
    session: AsyncSession,
    save_fixture: SaveFixture,
    generate_magic_link_token: GenerateMagicLinkToken,
) -> None:
    user = User(email="user@example.com")
    await save_fixture(user)

    # then
    session.expunge_all()

    magic_link, token = await generate_magic_link_token(user.email, user.id, None)

    authenticated_user, _ = await magic_link_service.authenticate(session, token)
    assert authenticated_user.id == user.id
    assert authenticated_user.email_verified

    deleted_magic_link = await magic_link_service.get(session, magic_link.id)
    assert deleted_magic_link is None


@pytest.mark.asyncio
async def test_authenticate_existing_user_unlinked_from_magic_token(
    session: AsyncSession,
    save_fixture: SaveFixture,
    generate_magic_link_token: GenerateMagicLinkToken,
) -> None:
    user = User(email="user@example.com")
    await save_fixture(user)

    # then
    session.expunge_all()

    magic_link, token = await generate_magic_link_token("user@example.com", None, None)

    authenticated_user, _ = await magic_link_service.authenticate(session, token)
    assert authenticated_user.id == user.id
    assert authenticated_user.email_verified

    deleted_magic_link = await magic_link_service.get(session, magic_link.id)
    assert deleted_magic_link is None


@pytest.mark.asyncio
async def test_authenticate_new_user(
    session: AsyncSession, generate_magic_link_token: GenerateMagicLinkToken
) -> None:
    # then
    session.expunge_all()

    magic_link, token = await generate_magic_link_token("user@example.com", None, None)

    authenticated_user, _ = await magic_link_service.authenticate(session, token)
    assert authenticated_user.email == magic_link.user_email
    assert authenticated_user.email_verified

    deleted_magic_link = await magic_link_service.get(session, magic_link.id)
    assert deleted_magic_link is None


@pytest.mark.asyncio
async def test_delete_expired(
    session: AsyncSession, generate_magic_link_token: GenerateMagicLinkToken
) -> None:
    # then
    session.expunge_all()

    magic_link_expired_1, _ = await generate_magic_link_token(
        "user@example.com",
        None,
        datetime(1900, 1, 1, tzinfo=UTC),
    )
    magic_link_expired_2, _ = await generate_magic_link_token(
        "user@example.com",
        None,
        datetime.now(UTC) - timedelta(seconds=1),
    )
    magic_link_valid, _ = await generate_magic_link_token(
        "user@example.com", None, None
    )

    await magic_link_service.delete_expired(session)

    assert await magic_link_service.get(session, magic_link_expired_1.id) is None
    assert await magic_link_service.get(session, magic_link_expired_2.id) is None
    assert await magic_link_service.get(session, magic_link_valid.id) is not None
