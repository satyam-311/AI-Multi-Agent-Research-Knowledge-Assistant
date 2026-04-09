import logging
import os
import secrets
import smtplib
import time
from email.message import EmailMessage

import bcrypt
from fastapi import Header, HTTPException
from sqlalchemy.orm import Session

from backend.auth.jwt_handler import decode_access_token
from backend.auth.models import AuthUser
from backend.database import SessionLocal

logger = logging.getLogger(__name__)

OTP_TTL_SECONDS = 5 * 60
_pending_signups: dict[str, dict[str, str | int]] = {}


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))


def generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _smtp_username() -> str:
    return os.getenv("GMAIL_SMTP_USERNAME", "").strip()


def _smtp_password() -> str:
    return os.getenv("GMAIL_SMTP_APP_PASSWORD", "").strip()


def _smtp_sender() -> str:
    return os.getenv("GMAIL_SMTP_SENDER", _smtp_username()).strip()


def _suppress_email() -> bool:
    return os.getenv("AUTH_EMAIL_SUPPRESS_SEND", "true").strip().lower() in {"1", "true", "yes"}


def store_pending_signup(full_name: str, email: str, password: str) -> int:
    otp = generate_otp()
    expires_at = int(time.time()) + OTP_TTL_SECONDS
    _pending_signups[email] = {
        "full_name": full_name,
        "email": email,
        "hashed_password": hash_password(password),
        "otp": otp,
        "expires_at": expires_at,
    }
    send_otp_email(email=email, full_name=full_name, otp=otp)
    return OTP_TTL_SECONDS


def resend_signup_otp(email: str) -> int:
    pending = _pending_signups.get(email)
    if pending is None:
        raise HTTPException(status_code=404, detail="No pending signup found for this email.")

    otp = generate_otp()
    expires_at = int(time.time()) + OTP_TTL_SECONDS
    pending["otp"] = otp
    pending["expires_at"] = expires_at
    send_otp_email(email=email, full_name=str(pending["full_name"]), otp=otp)
    return OTP_TTL_SECONDS


def verify_signup_otp(db: Session, email: str, otp: str) -> AuthUser:
    pending = _pending_signups.get(email)
    if pending is None:
        raise HTTPException(status_code=404, detail="No pending signup found for this email.")

    if int(pending["expires_at"]) < int(time.time()):
        _pending_signups.pop(email, None)
        raise HTTPException(status_code=400, detail="OTP expired. Please request a new one.")

    if str(pending["otp"]) != otp:
        raise HTTPException(status_code=400, detail="Invalid OTP.")

    existing = db.query(AuthUser).filter(AuthUser.email == email).first()
    if existing is not None:
        _pending_signups.pop(email, None)
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    user = AuthUser(
        name=str(pending["full_name"]),
        email=email,
        hashed_password=str(pending["hashed_password"]),
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    _pending_signups.pop(email, None)
    return user


def send_otp_email(email: str, full_name: str, otp: str) -> None:
    if _suppress_email():
        logger.info("OTP for %s (%s): %s", full_name, email, otp)
        return

    username = _smtp_username()
    password = _smtp_password()
    sender = _smtp_sender()
    if not username or not password or not sender:
        raise HTTPException(
            status_code=500,
            detail="Gmail SMTP is not configured. Set GMAIL_SMTP_USERNAME, GMAIL_SMTP_APP_PASSWORD, and GMAIL_SMTP_SENDER.",
        )

    message = EmailMessage()
    message["Subject"] = "Your verification code"
    message["From"] = sender
    message["To"] = email
    message.set_content(
        "\n".join(
            [
                f"Hello {full_name},",
                "",
                f"Your verification code is {otp}.",
                "It expires in 5 minutes.",
                "",
                "If you did not request this, you can ignore this email.",
            ]
        )
    )

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as server:
            server.starttls()
            server.login(username, password)
            server.send_message(message)
    except smtplib.SMTPException as exc:
        raise HTTPException(status_code=502, detail="Failed to send OTP email.") from exc


def get_current_user(authorization: str | None = Header(default=None)) -> AuthUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required.")

    token = authorization.split(" ", 1)[1].strip()
    payload = decode_access_token(token)

    db = SessionLocal()
    try:
        user = db.query(AuthUser).filter(AuthUser.id == int(payload["sub"])).first()
        if user is None or not user.is_verified:
            raise HTTPException(status_code=401, detail="User session is invalid.")
        db.expunge(user)
        return user
    finally:
        db.close()
