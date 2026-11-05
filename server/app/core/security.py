import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import get_settings

ALGORITHM = "HS256"
_PBKDF_ROUNDS = 120_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), _PBKDF_ROUNDS
    ).hex()
    return f"pbkdf2_sha256${_PBKDF_ROUNDS}${salt}${digest}"


def verify_password(plain: str, hashed: str) -> bool:
    try:
        algo, rounds_s, salt, digest = hashed.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        rounds = int(rounds_s)
        check = hashlib.pbkdf2_hmac(
            "sha256", plain.encode("utf-8"), salt.encode("utf-8"), rounds
        ).hex()
        return hmac.compare_digest(check, digest)
    except Exception:
        return False


def create_access_token(*, user_id: int, username: str, hours: int = 72) -> str:
    settings = get_settings()
    payload = {
        "sub": str(user_id),
        "username": username,
        "exp": datetime.now(timezone.utc) + timedelta(hours=hours),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    settings = get_settings()
    return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
