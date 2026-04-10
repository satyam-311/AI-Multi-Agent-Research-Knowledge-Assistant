from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

import schemas
from database import get_db
from services.auth_service import AuthService, get_auth_cookie, get_bearer_token

router = APIRouter()
auth_service = AuthService()


def _set_auth_cookie(response: Response, token: str) -> None:
    secure_cookie = auth_service.settings.environment == "production"
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=secure_cookie,
        samesite="lax",
        max_age=7 * 24 * 60 * 60,
        path="/",
    )


@router.post("/register", response_model=schemas.AuthResponse)
def register(
    payload: schemas.RegisterRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> schemas.AuthResponse:
    user = auth_service.register_user(
        db=db, name=payload.name, email=payload.email, password=payload.password
    )
    token = auth_service.create_token(user)
    _set_auth_cookie(response, token)
    return schemas.AuthResponse(token=token, user=user)


@router.post("/login", response_model=schemas.AuthResponse)
def login(
    payload: schemas.LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> schemas.AuthResponse:
    user = auth_service.login_user(db=db, email=payload.email, password=payload.password)
    token = auth_service.create_token(user)
    _set_auth_cookie(response, token)
    return schemas.AuthResponse(token=token, user=user)


@router.post("/google", response_model=schemas.AuthResponse)
def google_login(
    payload: schemas.GoogleLoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> schemas.AuthResponse:
    user = auth_service.login_with_google(db=db, id_token=payload.id_token)
    token = auth_service.create_token(user)
    _set_auth_cookie(response, token)
    return schemas.AuthResponse(token=token, user=user)


@router.get("/me", response_model=schemas.UserOut)
def me(
    authorization: str | None = Depends(get_bearer_token),
    access_token: str | None = Depends(get_auth_cookie),
    db: Session = Depends(get_db),
) -> schemas.UserOut:
    user = auth_service.get_current_user(
        db=db, authorization=authorization, access_token=access_token
    )
    return user


@router.post("/logout")
def logout(response: Response) -> dict[str, bool]:
    response.delete_cookie(key="access_token", path="/")
    return {"logged_out": True}
