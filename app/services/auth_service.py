from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    generate_token,
    hash_token,
    verify_password,
    verify_token,
)
from app.db.models import AdminDB
from app.db.services.crud_admin import admin_crud
from app.db.services.crud_refresh_token import refresh_token_crud
from app.exceptions.base import ApplicationException
from app.schema.auth import (
    AdminLoginRequest,
    AdminLoginResponse,
    LogoutResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
)

INVALID_ADMIN_CREDENTIALS = "Invalid admin credentials"
INVALID_REFRESH_TOKEN = "Invalid or expired refresh token"


class AuthService:
    async def login(
        self,
        db: AsyncSession,
        *,
        request: AdminLoginRequest,
    ) -> AdminLoginResponse:
        """Authenticate an admin and issue an access token plus a refresh token.

        Unknown username, wrong password and deactivated account all fail the
        same way so the response never reveals which check rejected the login.
        Logging in replaces any previous refresh token, so only the newest
        session stays valid.
        """
        admin = await admin_crud.get_by_username(db, request.username)
        if (
            admin is None
            or not admin.is_active
            or not verify_password(request.password, admin.password_hash)
        ):
            raise ApplicationException(
                message=INVALID_ADMIN_CREDENTIALS,
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

        refresh_token = generate_token(settings.refresh_token_bytes)
        await refresh_token_crud.replace_for_admin(
            db,
            admin_id=admin.id,
            hashed_refresh_token=hash_token(refresh_token),
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=settings.refresh_token_expire_days),
        )

        return AdminLoginResponse(
            accessToken=create_access_token(admin.username),
            refreshToken=refresh_token,
            expiresIn=settings.access_token_expires_in_seconds,
            refreshExpiresIn=settings.refresh_token_expires_in_seconds,
        )

    async def refresh(
        self,
        db: AsyncSession,
        *,
        request: RefreshTokenRequest,
    ) -> RefreshTokenResponse:
        """Issue a new access token for a stored, unexpired refresh token.

        The refresh token is deliberately not rotated: it stays valid until the
        admin logs in again, logs out, or it expires. Unknown, revoked, expired
        and deactivated-admin cases all fail identically.
        """
        stored = await refresh_token_crud.get_by_hashed_token(
            db, hash_token(request.refresh_token)
        )
        if stored is None or not verify_token(
            request.refresh_token, stored.hashed_refresh_token
        ):
            raise self._invalid_refresh_token()

        if self._is_expired(stored.expires_at):
            raise self._invalid_refresh_token()

        admin = await admin_crud.get_by_id(db, stored.admin_id)
        if admin is None or not admin.is_active:
            raise self._invalid_refresh_token()

        return RefreshTokenResponse(
            accessToken=create_access_token(admin.username),
            expiresIn=settings.access_token_expires_in_seconds,
        )

    async def logout(self, db: AsyncSession, *, current_admin: AdminDB) -> LogoutResponse:
        """Revoke the admin's refresh token.

        Deleting a token that is already gone is not an error, so repeated
        logouts stay idempotent.
        """
        await refresh_token_crud.delete_for_admin(db, admin_id=current_admin.id)
        return LogoutResponse()

    @staticmethod
    def _is_expired(expires_at: datetime) -> bool:
        # Rows written before the timezone-aware column existed, or read back
        # from a naive driver, are treated as UTC rather than crashing.
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return expires_at <= datetime.now(timezone.utc)

    @staticmethod
    def _invalid_refresh_token() -> ApplicationException:
        return ApplicationException(
            message=INVALID_REFRESH_TOKEN,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


auth_service = AuthService()


def get_auth_service() -> AuthService:
    return auth_service
