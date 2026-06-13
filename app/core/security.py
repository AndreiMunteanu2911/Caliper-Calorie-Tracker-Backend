from dataclasses import dataclass
from functools import lru_cache
import logging

import httpx
import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from app.core.config import Settings, get_settings

bearer_scheme = HTTPBearer(auto_error=False)
logger = logging.getLogger("caliper.auth")


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    id: str
    email: str | None


def _decode_token(token: str, settings: Settings) -> dict[str, object]:
    options = {"require": ["exp", "sub"]}
    algorithm = jwt.get_unverified_header(token).get("alg")

    if algorithm == "HS256":
        if not settings.supabase_jwt_secret:
            raise RuntimeError(
                "SUPABASE_JWT_SECRET is required for HS256 access tokens"
            )
        return jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
            options=options,
        )

    if algorithm in {"RS256", "ES256"}:
        if not settings.supabase_url:
            raise RuntimeError(
                "SUPABASE_URL is required for asymmetric access tokens"
            )
        signing_key = _get_jwk_client(
            settings.supabase_url
        ).get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=[algorithm],
            audience="authenticated",
            options=options,
        )

    raise RuntimeError(f"Unsupported Supabase JWT algorithm: {algorithm}")


@lru_cache(maxsize=4)
def _get_jwk_client(supabase_url: str) -> PyJWKClient:
    return PyJWKClient(
        f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
    )


async def _verify_with_supabase(
    token: str,
    api_key: str | None,
    settings: Settings,
) -> AuthenticatedUser | None:
    if not settings.supabase_url or not api_key:
        return None

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(
                f"{settings.supabase_url.rstrip('/')}/auth/v1/user",
                headers={
                    "apikey": api_key,
                    "Authorization": f"Bearer {token}",
                },
            )
    except httpx.HTTPError as exc:
        logger.warning(
            "Supabase token verification request failed: %s",
            type(exc).__name__,
        )
        return None

    if response.status_code != status.HTTP_200_OK:
        return None

    try:
        payload = response.json()
    except ValueError:
        return None
    subject = payload.get("id") if isinstance(payload, dict) else None
    if not isinstance(subject, str):
        return None
    email = payload.get("email")
    return AuthenticatedUser(
        id=subject,
        email=email if isinstance(email, str) else None,
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    supabase_api_key: str | None = Header(
        default=None,
        alias="X-Supabase-Api-Key",
    ),
    settings: Settings = Depends(get_settings),
) -> AuthenticatedUser:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )
    try:
        payload = _decode_token(credentials.credentials, settings)
    except (jwt.PyJWTError, RuntimeError) as exc:
        logger.warning(
            "Local bearer-token verification failed: %s",
            type(exc).__name__,
        )
        verified_user = await _verify_with_supabase(
            credentials.credentials,
            supabase_api_key,
            settings,
        )
        if verified_user is not None:
            return verified_user
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired bearer token",
        ) from exc

    subject = payload.get("sub")
    if not isinstance(subject, str):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token subject is invalid",
        )
    email = payload.get("email")
    return AuthenticatedUser(
        id=subject,
        email=email if isinstance(email, str) else None,
    )
