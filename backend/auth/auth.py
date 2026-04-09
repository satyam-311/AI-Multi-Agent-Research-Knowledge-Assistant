import logging
import time

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field

from backend.auth.utils import (
    get_cookie_name,
    get_cookie_secure,
    get_otp_ttl_seconds,
    get_session_ttl_seconds,
    normalize_email,
    otp_store,
    session_manager,
    should_expose_otp,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


class SendOTPRequest(BaseModel):
    email: str = Field(..., examples=["user@example.com"])


class VerifyOTPRequest(BaseModel):
    email: str = Field(..., examples=["user@example.com"])
    otp: str = Field(..., min_length=4, max_length=8, examples=["123456"])


@router.post("/send-otp")
def send_otp(payload: SendOTPRequest) -> dict[str, str | int]:
    email = normalize_email(payload.email)
    otp, expires_at = otp_store.create(email)
    logger.info("OTP requested for %s", email)

    response: dict[str, str | int] = {
        "message": "OTP generated successfully.",
        "email": email,
        "expires_in": max(0, expires_at - int(time.time())),
    }
    if should_expose_otp():
        response["otp"] = otp
    return response


@router.post("/verify-otp")
def verify_otp(payload: VerifyOTPRequest, response: Response) -> dict[str, str | int]:
    email = normalize_email(payload.email)
    otp_store.verify(email, payload.otp)
    token, expires_at = session_manager.create_token(email)

    response.set_cookie(
        key=get_cookie_name(),
        value=token,
        httponly=True,
        secure=get_cookie_secure(),
        samesite="lax",
        max_age=get_session_ttl_seconds(),
        path="/",
    )
    return {
        "message": "Authentication successful.",
        "email": email,
        "access_token": token,
        "token_type": "bearer",
        "expires_in": max(0, expires_at - int(time.time())),
    }
