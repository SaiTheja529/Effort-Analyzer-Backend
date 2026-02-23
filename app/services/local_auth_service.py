import base64
import hashlib
import hmac
import json
import re
import secrets
import time

from fastapi import HTTPException

from app.core.config import settings


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class LocalAuthService:
    PASSWORD_MIN_LENGTH = 8
    PBKDF2_ITERATIONS = 210_000

    @staticmethod
    def normalize_email(email: str) -> str:
        normalized = (email or "").strip().lower()
        if not _EMAIL_RE.fullmatch(normalized):
            raise HTTPException(400, "Invalid email address")
        return normalized

    @classmethod
    def validate_password(cls, password: str) -> None:
        if len((password or "").strip()) < cls.PASSWORD_MIN_LENGTH:
            raise HTTPException(
                400,
                f"Password must be at least {cls.PASSWORD_MIN_LENGTH} characters long",
            )

    @classmethod
    def hash_password(cls, password: str) -> str:
        cls.validate_password(password)
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            cls.PBKDF2_ITERATIONS,
        )
        return (
            f"pbkdf2_sha256${cls.PBKDF2_ITERATIONS}$"
            f"{cls._b64url_encode(salt)}${cls._b64url_encode(digest)}"
        )

    @classmethod
    def verify_password(cls, password: str, encoded_hash: str) -> bool:
        try:
            algorithm, rounds_str, salt_b64, hash_b64 = encoded_hash.split("$", 3)
            if algorithm != "pbkdf2_sha256":
                return False

            rounds = int(rounds_str)
            salt = cls._b64url_decode(salt_b64)
            expected = cls._b64url_decode(hash_b64)
        except Exception:
            return False

        candidate = hashlib.pbkdf2_hmac(
            "sha256",
            (password or "").encode("utf-8"),
            salt,
            rounds,
        )
        return hmac.compare_digest(candidate, expected)

    @classmethod
    def create_access_token(cls, user_id: int) -> str:
        exp = int(time.time()) + (settings.AUTH_TOKEN_EXPIRE_MINUTES * 60)
        payload = {"sub": str(user_id), "provider": "local", "exp": exp}
        payload_bytes = json.dumps(
            payload,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        payload_b64 = cls._b64url_encode(payload_bytes)
        signature = hmac.new(
            settings.AUTH_SECRET_KEY.encode("utf-8"),
            payload_b64.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return f"{payload_b64}.{cls._b64url_encode(signature)}"

    @classmethod
    def parse_access_token(cls, token: str) -> int:
        if "." not in token:
            raise HTTPException(401, "Invalid authentication token")

        payload_b64, signature_b64 = token.split(".", 1)
        expected_sig = hmac.new(
            settings.AUTH_SECRET_KEY.encode("utf-8"),
            payload_b64.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        try:
            provided_sig = cls._b64url_decode(signature_b64)
        except Exception:
            raise HTTPException(401, "Invalid authentication token")

        if not hmac.compare_digest(expected_sig, provided_sig):
            raise HTTPException(401, "Invalid authentication token")

        try:
            payload = json.loads(cls._b64url_decode(payload_b64).decode("utf-8"))
            exp = int(payload["exp"])
            user_id = int(payload["sub"])
            provider = payload.get("provider")
        except Exception:
            raise HTTPException(401, "Invalid authentication token")

        if provider != "local":
            raise HTTPException(401, "Unsupported authentication provider")
        if exp < int(time.time()):
            raise HTTPException(401, "Authentication token expired")
        return user_id

    @staticmethod
    def _b64url_encode(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")

    @staticmethod
    def _b64url_decode(data: str) -> bytes:
        padding = "=" * (-len(data) % 4)
        return base64.urlsafe_b64decode((data + padding).encode("utf-8"))
