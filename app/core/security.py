from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from app.core.config import settings

# bcrypt silently ignores everything past 72 bytes, so longer input is rejected
# at the API boundary rather than being truncated into a weaker password.
MAX_PASSWORD_BYTES = 72

_password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def generate_token(token_bytes: int | None = None) -> str:
    return secrets.token_urlsafe(token_bytes or settings.seed_client_token_bytes)


def hash_token(token: str, algorithm: str | None = None) -> str:
    hash_algorithm = algorithm or settings.client_token_hash_algorithm
    digest = hashlib.new(hash_algorithm)
    digest.update(token.encode("utf-8"))
    return f"{hash_algorithm}${digest.hexdigest()}"


def verify_token(token: str, hashed_token: str) -> bool:
    algorithm, _, expected_digest = hashed_token.partition("$")
    if not algorithm or not expected_digest:
        return False

    try:
        digest = hashlib.new(algorithm)
    except ValueError:
        return False
    digest.update(token.encode("utf-8"))
    candidate = digest.hexdigest()
    return hmac.compare_digest(candidate, expected_digest)


def hash_password(password: str) -> str:
    """Hash an admin password with bcrypt. The plaintext is never persisted."""
    return _password_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its bcrypt hash, returning False when malformed."""
    try:
        return _password_context.verify(password, password_hash)
    except (ValueError, TypeError):
        return False


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    """Issue a signed admin access token carrying sub, iat and exp claims."""
    issued_at = datetime.now(timezone.utc)
    expires_at = issued_at + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )
    payload = {"sub": subject, "iat": issued_at, "exp": expires_at}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def verify_access_token(token: str) -> str | None:
    """Return the subject of a valid access token, or None when it is not usable.

    Signature failures, expiry, missing claims and malformed tokens are all
    reported the same way so callers cannot leak which check rejected the token.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.InvalidTokenError:
        return None

    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject.strip():
        return None
    return subject
