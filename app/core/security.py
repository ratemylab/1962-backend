from __future__ import annotations

import hashlib
import hmac
import secrets

from app.core.config import settings


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
