import hashlib
import secrets
import time

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Employee,
    TelegramLinkAttempt,
    TelegramLinkCode,
    TelegramUserLink,
)


LINK_CODE_TTL_SECONDS = 600
MAX_LINK_ATTEMPTS = 5
LINK_ATTEMPT_LOCK_SECONDS = 600
class TelegramLinkError(Exception):
    """Expected error during Telegram account linking."""

    def __init__(self, error_code: str):
        self.error_code = error_code
        super().__init__(error_code)


def hash_link_code(code: str) -> str:
    """Hash a one-time linking code before storing it."""
    return hashlib.sha256(code.strip().encode("utf-8")).hexdigest()


def issue_link_code(db: Session, employee_id: int) -> str:
    """Create a one-time code for an existing, unlinked employee."""

    employee = db.get(Employee, employee_id)

    if employee is None:
        raise TelegramLinkError("employee_not_found")

    existing_link = (
        db.query(TelegramUserLink)
        .filter(TelegramUserLink.employee_id == employee_id)
        .first()
    )

    if existing_link is not None:
        raise TelegramLinkError("employee_already_linked")

    raw_code = f"{secrets.randbelow(1_000_000):06d}"

    record = TelegramLinkCode(
        code_hash=hash_link_code(raw_code),
        employee_id=employee_id,
        expires_at=int(time.time()) + LINK_CODE_TTL_SECONDS,
    )

    db.add(record)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise TelegramLinkError("could_not_issue_code") from exc

    return raw_code



def redeem_link_code(
    db: Session,
    telegram_user_id: int,
    code: str,
) -> int:
    if telegram_user_id <= 0:
        raise TelegramLinkError("invalid_telegram_user")

    code = code.strip()

    if len(code) != 6 or not code.isdigit():
        raise TelegramLinkError("invalid_or_expired")

    now = int(time.time())

    try:
        attempt = (
            db.query(TelegramLinkAttempt)
            .filter(
                TelegramLinkAttempt.telegram_user_id
                == telegram_user_id
            )
            .one_or_none()
        )

        # Block further attempts while the temporary lock is active.
        if attempt and attempt.locked_until > now:
            raise TelegramLinkError("too_many_attempts")

        # Reset the counter after the lock has expired.
        if attempt and attempt.locked_until:
            attempt.failed_attempts = 0
            attempt.locked_until = 0

        code_record = (
            db.query(TelegramLinkCode)
            .filter(
                TelegramLinkCode.code_hash
                == hash_link_code(code)
            )
            .one_or_none()
        )

        # Count invalid, used, and expired codes.
        if (
            code_record is None
            or code_record.used_at is not None
            or code_record.expires_at <= now
        ):
            if attempt is None:
                attempt = TelegramLinkAttempt(
                    telegram_user_id=telegram_user_id,
                    failed_attempts=0,
                    locked_until=0,
                )
                db.add(attempt)

            attempt.failed_attempts += 1

            locked = (
                attempt.failed_attempts >= MAX_LINK_ATTEMPTS
            )

            if locked:
                attempt.locked_until = (
                    now + LINK_ATTEMPT_LOCK_SECONDS
                )

            db.commit()

            if locked:
                raise TelegramLinkError("too_many_attempts")

            raise TelegramLinkError("invalid_or_expired")

        # A Telegram account can be linked only once.
        existing_telegram_link = (
            db.query(TelegramUserLink)
            .filter(
                TelegramUserLink.telegram_user_id
                == telegram_user_id
            )
            .first()
        )

        if existing_telegram_link:
            raise TelegramLinkError("telegram_already_linked")

        # An employee can be linked to only one Telegram account.
        existing_employee_link = (
            db.query(TelegramUserLink)
            .filter(
                TelegramUserLink.employee_id
                == code_record.employee_id
            )
            .first()
        )

        if existing_employee_link:
            raise TelegramLinkError("employee_already_linked")

        link = TelegramUserLink(
            telegram_user_id=telegram_user_id,
            employee_id=code_record.employee_id,
        )

        db.add(link)
        code_record.used_at = now

        if attempt:
            attempt.failed_attempts = 0
            attempt.locked_until = 0

        db.commit()
        return code_record.employee_id

    except IntegrityError as exc:
        db.rollback()
        raise TelegramLinkError("already_linked") from exc



def resolve_telegram_employee(
    db: Session,
    telegram_user_id: int,
) -> int | None:
    """Return the linked employee ID, or None if the account is unlinked."""

    link = (
        db.query(TelegramUserLink)
        .filter(TelegramUserLink.telegram_user_id == telegram_user_id)
        .first()
    )

    return link.employee_id if link is not None else None