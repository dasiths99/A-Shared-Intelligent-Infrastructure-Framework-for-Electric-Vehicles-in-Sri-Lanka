"""Password hashing (PBKDF2-SHA256, salted) and bearer-token auth for C1."""

import hashlib
import hmac
import secrets

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .db import get_db
from .models import User

ITER = 200_000


def hash_password(pw: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), ITER).hex()
    return f"pbkdf2${ITER}${salt}${dk}"


def verify_password(pw: str, stored: str) -> bool:
    _, it, salt, dk = stored.split("$")
    test = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), int(it)).hex()
    return hmac.compare_digest(test, dk)


def new_token() -> str:
    return secrets.token_urlsafe(32)


def current_user(authorization: str = Header(default=""), db: Session = Depends(get_db)) -> User:
    token = authorization.removeprefix("Bearer ").strip()
    user = db.query(User).filter(User.token == token).first() if token else None
    if not user:
        raise HTTPException(401, "login required")
    return user
