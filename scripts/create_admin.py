"""
Bootstrap the first admin account in a fresh environment (ops-only).

Usage:
  ALLOW_ADMIN_BOOTSTRAP=true python -m scripts.create_admin --email admin@ptc.edu
  ALLOW_ADMIN_BOOTSTRAP=true python -m scripts.create_admin --email admin@ptc.edu --password 'YourSecurePass123!'

Password resolution order:
  1. --password CLI flag
  2. ADMIN_BOOTSTRAP_PASSWORD environment variable
  3. Interactive prompt (hidden)
"""

from __future__ import annotations

import argparse
import getpass
import os
import secrets
import string

from app.core.database import SessionLocal
from app.core.exceptions import ConflictError
from app.services.user_admin_service import UserAdminService

MIN_PASSWORD_LENGTH = 8


def _require_bootstrap_enabled() -> None:
    if os.environ.get("ALLOW_ADMIN_BOOTSTRAP", "").lower() != "true":
        raise SystemExit(
            "Refusing to bootstrap admin: set ALLOW_ADMIN_BOOTSTRAP=true in the environment."
        )


def _resolve_password(cli_password: str | None) -> str:
    if cli_password:
        password = cli_password
    else:
        env_password = os.environ.get("ADMIN_BOOTSTRAP_PASSWORD")
        if env_password:
            password = env_password
        else:
            password = getpass.getpass("Admin password: ")
            confirm = getpass.getpass("Confirm password: ")
            if password != confirm:
                raise SystemExit("Passwords do not match.")

    if len(password) < MIN_PASSWORD_LENGTH:
        raise SystemExit(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    return password


def _generate_password(length: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def create_admin_account(*, email: str, password: str | None, generate: bool) -> None:
    _require_bootstrap_enabled()

    if generate:
        resolved_password = _generate_password()
        generated = True
    else:
        resolved_password = _resolve_password(password)
        generated = False

    db = SessionLocal()
    try:
        user = UserAdminService(db).create_admin(
            email=email,
            password=resolved_password,
            bootstrap=True,
        )
        print(f"Created admin account: {user.email} (id={user.id})")
        if generated:
            print("Generated password (store securely; it will not be shown again):")
            print(resolved_password)
        else:
            print("Admin account is active. Share credentials through a secure channel.")
    except ConflictError as exc:
        raise SystemExit(exc.message) from exc
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap the first admin account.")
    parser.add_argument("--email", required=True, help="Admin email address")
    parser.add_argument(
        "--password",
        help="Admin password (optional; otherwise ADMIN_BOOTSTRAP_PASSWORD or prompt)",
    )
    parser.add_argument(
        "--generate-password",
        action="store_true",
        help="Generate a random password and print it once",
    )
    args = parser.parse_args()

    create_admin_account(
        email=args.email.strip().lower(),
        password=args.password,
        generate=args.generate_password,
    )


if __name__ == "__main__":
    main()
