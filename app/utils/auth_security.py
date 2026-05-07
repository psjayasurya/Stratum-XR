"""
Auth Security Helpers
Reusable helpers for CSRF, JWT session rotation, and cookie management.
"""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Optional, Tuple

from fastapi import HTTPException, Request
from jose import JWTError, jwt

from app.config import config
from app.database import get_db

ACCESS_COOKIE_NAME = "access_token"
REFRESH_COOKIE_NAME = "refresh_token"
CSRF_COOKIE_NAME = "csrf_token"
USER_EMAIL_COOKIE_NAME = "user_email"
REFRESH_SESSION_TABLE = "auth_sessions"


def _utcnow() -> datetime:
    return datetime.utcnow()


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def ensure_csrf_token(request: Request) -> str:
    existing = request.cookies.get(CSRF_COOKIE_NAME)
    return existing or generate_csrf_token()


def validate_csrf(request: Request, submitted_token: Optional[str]) -> None:
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    header_token = request.headers.get("x-csrf-token")
    token = submitted_token or header_token

    if not cookie_token or not token:
        raise HTTPException(status_code=403, detail="CSRF token missing")

    if not secrets.compare_digest(cookie_token, token):
        raise HTTPException(status_code=403, detail="CSRF token invalid")


def _token_payload(email: str, token_type: str, expires_delta: timedelta, token_version: int) -> dict:
    issued_at = _utcnow()
    return {
        "sub": email,
        "typ": token_type,
        "iat": issued_at,
        "exp": issued_at + expires_delta,
        "jti": uuid.uuid4().hex,
        "ver": int(token_version or 0),
    }


def create_access_token(email: str, token_version: int = 0, expires_delta: Optional[timedelta] = None) -> str:
    payload = _token_payload(
        email=email,
        token_type="access",
        expires_delta=expires_delta or config.JWT_ACCESS_TOKEN_EXPIRES,
        token_version=token_version,
    )
    return jwt.encode(payload, config.JWT_PRIVATE_KEY, algorithm=config.JWT_ALGORITHM)


def create_refresh_token(email: str, token_version: int = 0, expires_delta: Optional[timedelta] = None) -> str:
    payload = _token_payload(
        email=email,
        token_type="refresh",
        expires_delta=expires_delta or config.JWT_REFRESH_TOKEN_EXPIRES,
        token_version=token_version,
    )
    return jwt.encode(payload, config.JWT_PRIVATE_KEY, algorithm=config.JWT_ALGORITHM)


def _decode_token(token: str, expected_type: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, config.JWT_PUBLIC_KEY, algorithms=[config.JWT_ALGORITHM])
        if payload.get("typ") != expected_type:
            return None
        email = payload.get("sub")
        if not email:
            return None
        return payload
    except JWTError:
        return None


def get_user_token_version(email: str) -> int:
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("SELECT COALESCE(token_version, 0) FROM users WHERE email = %s", (email,))
        row = cur.fetchone()
        return int(row[0]) if row and row[0] is not None else 0
    finally:
        db.close()


def verify_access_token(token: str) -> Optional[str]:
    payload = _decode_token(token, "access")
    if not payload:
        return None

    email = payload["sub"]
    if int(payload.get("ver", 0)) != get_user_token_version(email):
        return None

    return email


def verify_refresh_token(token: str) -> Optional[dict]:
    payload = _decode_token(token, "refresh")
    if not payload:
        return None

    email = payload["sub"]
    if int(payload.get("ver", 0)) != get_user_token_version(email):
        return None

    return payload


def _refresh_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_refresh_session(refresh_token: str, request: Optional[Request] = None) -> None:
    payload = verify_refresh_token(refresh_token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    db = get_db()
    try:
        cur = db.cursor()
        cur.execute(
            f"""
            INSERT INTO {REFRESH_SESSION_TABLE}
                (session_jti, user_email, token_hash, expires_at, user_agent, ip_address)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                payload["jti"],
                payload["sub"],
                _refresh_token_hash(refresh_token),
                datetime.utcfromtimestamp(int(payload["exp"])),
                (request.headers.get("user-agent", "") if request else "")[:255],
                (request.client.host if request and request.client else "")[:255],
            ),
        )
        db.commit()
    finally:
        db.close()


def validate_refresh_session(refresh_token: str) -> Optional[str]:
    payload = verify_refresh_token(refresh_token)
    if not payload:
        return None

    db = get_db()
    try:
        cur = db.cursor()
        cur.execute(
            f"""
            SELECT user_email
            FROM {REFRESH_SESSION_TABLE}
            WHERE session_jti = %s
              AND user_email = %s
              AND token_hash = %s
              AND revoked_at IS NULL
              AND expires_at > CURRENT_TIMESTAMP
            """,
            (payload["jti"], payload["sub"], _refresh_token_hash(refresh_token)),
        )
        row = cur.fetchone()
        if not row:
            return None

        cur.execute(
            f"UPDATE {REFRESH_SESSION_TABLE} SET last_used_at = CURRENT_TIMESTAMP WHERE session_jti = %s",
            (payload["jti"],),
        )
        db.commit()
        return row[0]
    finally:
        db.close()


def revoke_refresh_session(refresh_token: str) -> None:
    payload = _decode_token(refresh_token, "refresh")
    if not payload:
        return

    db = get_db()
    try:
        cur = db.cursor()
        cur.execute(
            f"UPDATE {REFRESH_SESSION_TABLE} SET revoked_at = CURRENT_TIMESTAMP WHERE session_jti = %s",
            (payload["jti"],),
        )
        db.commit()
    finally:
        db.close()


def revoke_user_refresh_sessions(email: str) -> None:
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute(
            f"UPDATE {REFRESH_SESSION_TABLE} SET revoked_at = CURRENT_TIMESTAMP WHERE user_email = %s AND revoked_at IS NULL",
            (email,),
        )
        db.commit()
    finally:
        db.close()


def increment_user_token_version(email: str) -> None:
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute(
            "UPDATE users SET token_version = COALESCE(token_version, 0) + 1 WHERE email = %s",
            (email,),
        )
        db.commit()
    finally:
        db.close()


def set_auth_cookies(response, access_token: str, refresh_token: str, email: str, csrf_token: str) -> None:
    cookie_secure = bool(config.COOKIE_SECURE)
    same_site = config.COOKIE_SAMESITE
    access_max_age = int(config.JWT_ACCESS_TOKEN_EXPIRES.total_seconds())
    refresh_max_age = int(config.JWT_REFRESH_TOKEN_EXPIRES.total_seconds())

    response.set_cookie(
        key=ACCESS_COOKIE_NAME,
        value=access_token,
        httponly=True,
        secure=cookie_secure,
        samesite=same_site,
        max_age=access_max_age,
        path="/",
    )
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=cookie_secure,
        samesite=same_site,
        max_age=refresh_max_age,
        path="/",
    )
    response.set_cookie(
        key=USER_EMAIL_COOKIE_NAME,
        value=email,
        httponly=False,
        secure=cookie_secure,
        samesite=same_site,
        max_age=refresh_max_age,
        path="/",
    )
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        httponly=False,
        secure=cookie_secure,
        samesite=same_site,
        max_age=refresh_max_age,
        path="/",
    )


def clear_auth_cookies(response) -> None:
    for cookie_name in (ACCESS_COOKIE_NAME, REFRESH_COOKIE_NAME, USER_EMAIL_COOKIE_NAME, CSRF_COOKIE_NAME):
        response.delete_cookie(cookie_name, path="/")


__all__ = [
    "ACCESS_COOKIE_NAME",
    "CSRF_COOKIE_NAME",
    "REFRESH_COOKIE_NAME",
    "USER_EMAIL_COOKIE_NAME",
    "clear_auth_cookies",
    "create_access_token",
    "create_refresh_session",
    "create_refresh_token",
    "ensure_csrf_token",
    "generate_csrf_token",
    "increment_user_token_version",
    "revoke_refresh_session",
    "revoke_user_refresh_sessions",
    "set_auth_cookies",
    "validate_csrf",
    "validate_refresh_session",
    "verify_access_token",
    "verify_refresh_token",
]
