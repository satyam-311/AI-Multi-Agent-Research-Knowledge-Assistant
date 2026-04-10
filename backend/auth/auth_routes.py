from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth.auth_utils import resend_signup_otp, store_pending_signup, verify_password, verify_signup_otp
from auth.jwt_handler import create_access_token
from auth.models import AuthUser
from auth.schemas import (
    AuthTokenResponse,
    LoginRequest,
    OTPResponse,
    RegisterResponse,
    ResendOTPRequest,
    SignupRequest,
    VerifyOTPRequest,
)
from database import get_db

router = APIRouter()


def _serialize_user(user: AuthUser) -> dict[str, str | int | bool]:
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "is_verified": user.is_verified,
        "created_at": user.created_at.isoformat() if user.created_at else "",
    }


@router.post("/register", response_model=RegisterResponse)
def register(payload: SignupRequest, db: Session = Depends(get_db)) -> RegisterResponse:
    existing = db.query(AuthUser).filter(AuthUser.email == payload.email).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    expires_in = store_pending_signup(
        full_name=payload.full_name,
        email=payload.email,
        password=payload.password,
    )
    return RegisterResponse(
        message="OTP sent to your Gmail address. Verify to complete signup.",
        email=payload.email,
        expires_in=expires_in,
    )


@router.post("/send-otp", response_model=OTPResponse)
def send_otp(payload: ResendOTPRequest) -> OTPResponse:
    expires_in = resend_signup_otp(payload.email)
    return OTPResponse(
        message="OTP resent successfully.",
        email=payload.email,
        expires_in=expires_in,
    )


@router.post("/verify-otp", response_model=AuthTokenResponse)
def verify_otp(
    payload: VerifyOTPRequest,
    db: Session = Depends(get_db),
) -> AuthTokenResponse:
    user = verify_signup_otp(db=db, email=payload.email, otp=payload.otp)
    token = create_access_token(user_id=user.id, email=user.email)
    return AuthTokenResponse(access_token=token, user=_serialize_user(user))


@router.post("/login", response_model=AuthTokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> AuthTokenResponse:
    user = db.query(AuthUser).filter(AuthUser.email == payload.email).first()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Email is not verified.")

    token = create_access_token(user_id=user.id, email=user.email)
    return AuthTokenResponse(access_token=token, user=_serialize_user(user))
