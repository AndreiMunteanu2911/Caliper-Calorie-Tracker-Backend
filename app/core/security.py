from dataclasses import dataclass
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from app.core.config import Settings, get_settings

bearer_scheme = HTTPBearer(auto_error=False)


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


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
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
