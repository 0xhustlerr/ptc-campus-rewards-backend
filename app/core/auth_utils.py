"""Shared auth helpers."""

from uuid import UUID

from app.core.exceptions import UnauthorizedError


def parse_user_id(subject: str | None) -> UUID:
    if not subject:
        raise UnauthorizedError()
    try:
        return UUID(str(subject))
    except (ValueError, TypeError, AttributeError):
        raise UnauthorizedError("Invalid token subject") from None
