"""Password hashing (bcrypt) and JWT creation / verification."""
import base64
import hashlib
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import get_settings


HASH_PREFIX = "$hw1$"


def _prepared(password: str) -> bytes:
    """bcrypt reads only the first 72 bytes, so two long passwords that start alike would be the same password. The whole password is first
    reduced to a fixed 44-byte digest, which bcrypt then reads in full."""
    return base64.b64encode(hashlib.sha256(password.encode()).digest())


def hash_password(password: str) -> str:
    return HASH_PREFIX + bcrypt.hashpw(_prepared(password), bcrypt.gensalt(rounds=get_settings().bcrypt_rounds)).decode()


def is_current_hash(hashed: str) -> bool:
    return hashed.startswith(HASH_PREFIX)


def verify_password(password: str, hashed: str) -> bool:
    """Passwords saved by an older version (plain bcrypt of the first 72 bytes) still work; they are re-saved in the new form at the next login."""
    try:
        if hashed.startswith(HASH_PREFIX):
            return bcrypt.checkpw(_prepared(password), hashed[len(HASH_PREFIX):].encode())
        return bcrypt.checkpw(password.encode()[:72], hashed.encode())
    except ValueError:
        return False


def password_fingerprint(password_hash: str) -> str:
    """Short fingerprint of the current password hash. A token carries it, so changing the password ends every older token."""
    return hashlib.sha256(password_hash.encode()).hexdigest()[:12]


def create_access_token(user_id: int, password_hash: str = "") -> str:
    settings = get_settings()
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": str(user_id), "exp": expires, "pv": password_fingerprint(password_hash)}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> tuple[int, str] | None:
    """(user id, password fingerprint) inside the token, or None if invalid/expired."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return int(payload["sub"]), str(payload.get("pv", ""))
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


def decode_access_token(token: str) -> int | None:
    """Return the user id inside the token, or None if invalid/expired."""
    decoded = decode_token(token)
    return decoded[0] if decoded else None
