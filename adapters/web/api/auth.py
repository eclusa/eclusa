from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from pydantic import BaseModel

JWT_ALGORITHM = "HS256"
JWT_DEFAULT_SECRET = "dev-secret-change-me"
security = HTTPBearer(auto_error=False)
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

router = APIRouter(prefix="/auth", tags=["auth"])

__all__ = ["router", "verify_token", "DEFAULT_PERMISSIONS"]

# Per-type default permissions (RFC §3.2)
DEFAULT_PERMISSIONS: dict[str, dict] = {
    "human": {"resolve_gates": ["*"], "view_costs": True},
    "agent": {"resolve_gates": [], "view_costs": False, "spawn_cascades": True},
    "system": {"resolve_gates": ["*"], "view_costs": True, "spawn_cascades": True},
    "webhook": {"resolve_gates": [], "view_costs": False},
}


class RegisterRequest(BaseModel):
    email: str
    name: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def get_jwt_secret() -> str:
    return os.environ.get("JWT_SECRET", JWT_DEFAULT_SECRET)


def _issue_token(actor_id: str, email: str, actor_type: str) -> str:
    payload = {
        "sub": actor_id,
        "email": email,
        "actor_type": actor_type,
        "exp": datetime.now(timezone.utc) + timedelta(hours=24),
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.post("/register", response_model=TokenResponse)
async def register(body: RegisterRequest, request: Request) -> TokenResponse:
    """Register a new human actor with email + password."""
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT id FROM actor WHERE identity = $1", body.email
        )
        if existing is not None:
            raise HTTPException(status_code=409, detail="Email already registered")

        actor_id = str(uuid.uuid4())
        hashed = pwd_context.hash(body.password)
        permissions = {
            **DEFAULT_PERMISSIONS["human"],
            "password_hash": hashed,
            "name": body.name,
        }
        await conn.execute(
            """
            INSERT INTO actor (id, type, identity, permissions)
            VALUES ($1::uuid, $2::actor_type, $3, $4::jsonb)
            """,
            actor_id,
            "human",
            body.email,
            json.dumps(permissions),
        )

    token = _issue_token(actor_id, body.email, "human")
    return TokenResponse(access_token=token)


@router.post("/token", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request) -> TokenResponse:
    """Authenticate with email + password."""
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, type, permissions FROM actor WHERE identity = $1",
            body.email,
        )
    if row is None:
        raise _unauthorized("Invalid credentials")

    permissions = row["permissions"]
    if isinstance(permissions, str):
        permissions = json.loads(permissions)

    password_hash = permissions.get("password_hash")
    if not password_hash or not pwd_context.verify(body.password, password_hash):
        raise _unauthorized("Invalid credentials")

    token = _issue_token(str(row["id"]), body.email, row["type"])
    return TokenResponse(access_token=token)


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized("Not authenticated")

    try:
        payload = jwt.decode(
            credentials.credentials,
            get_jwt_secret(),
            algorithms=[JWT_ALGORITHM],
        )
    except jwt.ExpiredSignatureError as exc:
        raise _unauthorized("Token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise _unauthorized("Invalid token") from exc

    if not isinstance(payload, dict):
        raise _unauthorized("Invalid token payload")

    # Reject legacy tokens that used hardcoded "operator"
    if payload.get("sub") == "operator" or "actor_type" not in payload:
        raise _unauthorized("Legacy token — re-authenticate")

    return payload
