import base64
import hashlib
import hmac
import json
import os
import time

from fastapi import HTTPException


def _urlsafe_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _urlsafe_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _jwt_secret() -> str:
    return os.getenv("AUTH_SECRET", "local-dev-secret-change-before-production").strip()


def _jwt_expiry_seconds() -> int:
    return max(300, int(os.getenv("AUTH_JWT_EXPIRES_SECONDS", str(24 * 60 * 60))))


def create_access_token(user_id: int, email: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": int(time.time()) + _jwt_expiry_seconds(),
    }
    header_b64 = _urlsafe_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _urlsafe_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}"
    signature = hmac.new(
        _jwt_secret().encode("utf-8"),
        signing_input.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return f"{signing_input}.{_urlsafe_encode(signature)}"


def decode_access_token(token: str) -> dict[str, str | int]:
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid token format.") from exc

    signing_input = f"{header_b64}.{payload_b64}"
    expected_signature = hmac.new(
        _jwt_secret().encode("utf-8"),
        signing_input.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    if not hmac.compare_digest(_urlsafe_encode(expected_signature), signature_b64):
        raise HTTPException(status_code=401, detail="Invalid token signature.")

    payload = json.loads(_urlsafe_decode(payload_b64).decode("utf-8"))
    if int(payload.get("exp", 0)) < int(time.time()):
        raise HTTPException(status_code=401, detail="Token expired.")
    return payload
