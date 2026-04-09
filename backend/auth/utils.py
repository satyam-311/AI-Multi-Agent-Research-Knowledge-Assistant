import base64
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import time
from collections.abc import Iterable

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _urlsafe_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _urlsafe_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if not EMAIL_PATTERN.match(normalized):
        raise HTTPException(status_code=400, detail="A valid email address is required.")
    return normalized


def get_auth_secret() -> str:
    return os.getenv("AUTH_SECRET", "local-dev-secret-change-before-production").strip()


def get_otp_ttl_seconds() -> int:
    return max(60, int(os.getenv("AUTH_OTP_TTL_SECONDS", "300")))


def get_session_ttl_seconds() -> int:
    return max(300, int(os.getenv("AUTH_SESSION_TTL_SECONDS", str(7 * 24 * 60 * 60))))


def get_cookie_name() -> str:
    return os.getenv("AUTH_COOKIE_NAME", "auth_token").strip() or "auth_token"


def get_cookie_secure() -> bool:
    return _get_bool("AUTH_COOKIE_SECURE", False)


def get_protected_prefixes() -> tuple[str, ...]:
    raw = os.getenv("AUTH_PROTECTED_PREFIXES", "/rag,/query,/research,/agent")
    prefixes = [prefix.strip() for prefix in raw.split(",") if prefix.strip()]
    return tuple(prefixes)


def should_expose_otp() -> bool:
    return _get_bool("AUTH_EXPOSE_TEST_OTP", True)


def _hash_value(value: str) -> str:
    return hmac.new(get_auth_secret().encode("utf-8"), value.encode("utf-8"), hashlib.sha256).hexdigest()


class OTPStore:
    def __init__(self) -> None:
        self._entries: dict[str, dict[str, int | str]] = {}

    def create(self, email: str) -> tuple[str, int]:
        normalized_email = normalize_email(email)
        otp = f"{secrets.randbelow(1_000_000):06d}"
        expires_at = int(time.time()) + get_otp_ttl_seconds()
        self._entries[normalized_email] = {
            "otp_hash": _hash_value(f"{normalized_email}:{otp}"),
            "expires_at": expires_at,
            "attempts": 0,
        }
        logger.info("Generated OTP for %s", normalized_email)
        return otp, expires_at

    def verify(self, email: str, otp: str) -> None:
        normalized_email = normalize_email(email)
        entry = self._entries.get(normalized_email)
        if entry is None:
            raise HTTPException(status_code=401, detail="OTP not found or already used.")

        now = int(time.time())
        expires_at = int(entry["expires_at"])
        if now > expires_at:
            self._entries.pop(normalized_email, None)
            raise HTTPException(status_code=401, detail="OTP expired.")

        attempts = int(entry["attempts"]) + 1
        entry["attempts"] = attempts
        if attempts > 5:
            self._entries.pop(normalized_email, None)
            raise HTTPException(status_code=401, detail="OTP attempts exceeded.")

        expected_hash = str(entry["otp_hash"])
        actual_hash = _hash_value(f"{normalized_email}:{otp.strip()}")
        if not hmac.compare_digest(actual_hash, expected_hash):
            raise HTTPException(status_code=401, detail="Invalid OTP.")

        self._entries.pop(normalized_email, None)


class SessionManager:
    def create_token(self, email: str) -> tuple[str, int]:
        normalized_email = normalize_email(email)
        expires_at = int(time.time()) + get_session_ttl_seconds()
        payload = {
            "email": normalized_email,
            "exp": expires_at,
        }
        payload_b64 = _urlsafe_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        signature = hmac.new(
            get_auth_secret().encode("utf-8"),
            payload_b64.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return f"{payload_b64}.{_urlsafe_encode(signature)}", expires_at

    def verify_token(self, token: str) -> dict[str, str | int]:
        try:
            payload_b64, signature_b64 = token.split(".", 1)
        except ValueError as exc:
            raise HTTPException(status_code=401, detail="Invalid authentication token.") from exc

        expected_signature = hmac.new(
            get_auth_secret().encode("utf-8"),
            payload_b64.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(_urlsafe_encode(expected_signature), signature_b64):
            raise HTTPException(status_code=401, detail="Invalid authentication token.")

        payload = json.loads(_urlsafe_decode(payload_b64).decode("utf-8"))
        if int(payload.get("exp", 0)) < int(time.time()):
            raise HTTPException(status_code=401, detail="Authentication token expired.")
        return payload


def extract_token(request: Request) -> str | None:
    authorization = request.headers.get("Authorization", "").strip()
    if authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()

    cookie_token = request.cookies.get(get_cookie_name())
    if cookie_token:
        return cookie_token
    return None


def path_matches_prefix(path: str, prefixes: Iterable[str]) -> bool:
    return any(path == prefix or path.startswith(f"{prefix}/") for prefix in prefixes)


otp_store = OTPStore()
session_manager = SessionManager()
