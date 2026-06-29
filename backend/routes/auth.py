# routes/auth.py
# FastAPI route handlers for MARKA user authentication.
# Provides email/password registration and login, Google OAuth via Firebase,
# session cookie management, current user lookup, and logout.

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from backend import schemas
# get_db provides a per-request SQLAlchemy session via FastAPI's dependency injection
from backend.database import get_db
# AuthService owns all credential logic; get_auth_cookie and get_bearer_token
# are FastAPI dependencies that extract the token from cookies and headers
from backend.services.auth_service import AuthService, get_auth_cookie, get_bearer_token

router = APIRouter()
# Single AuthService instance per worker process; Firebase Admin SDK is initialized here
auth_service = AuthService()


def _set_auth_cookie(response: Response, token: str) -> None:
    """
    Write the session JWT into an HttpOnly cookie on the response.

    HttpOnly prevents JavaScript from reading the token, which mitigates XSS attacks
    that attempt to steal session credentials. The Secure flag is enabled only in
    production (HTTPS) to avoid breaking local development over HTTP.

    Args:
        response (Response): The FastAPI Response object for the current request.
        token (str): The MARKA HMAC-SHA256 JWT to store in the cookie.

    Returns:
        None
    """
    # Enable Secure flag only in production so the cookie is HTTPS-only in deployment
    secure_cookie = auth_service.settings.environment == "production"
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=secure_cookie,
        # samesite="lax" permits the cookie on top-level navigations while blocking
        # most CSRF attack vectors without requiring a separate CSRF token
        samesite="lax",
        # Match the token expiry (7 days) so the cookie is not evicted before the token expires
        max_age=7 * 24 * 60 * 60,
        path="/",
    )


@router.post("/register", response_model=schemas.AuthResponse)
def register(
    payload: schemas.RegisterRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> schemas.AuthResponse:
    """
    Register a new user account with an email and password.

    Creates a new user row in PostgreSQL with a PBKDF2-SHA256 password hash,
    issues a signed JWT, and sets it as an HttpOnly session cookie.

    Args:
        payload (schemas.RegisterRequest): Validated name, email, and password fields.
        response (Response): FastAPI response object used to set the session cookie.
        db (Session): Per-request SQLAlchemy session injected by get_db.

    Returns:
        schemas.AuthResponse: The signed JWT token and the new user's profile.

    Raises:
        HTTPException 409: If an account with the submitted email already exists.
    """
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
    """
    Authenticate an existing user with email and password.

    Verifies the password against the stored PBKDF2-SHA256 hash using a
    constant-time comparison, then issues a new signed JWT session token.

    Args:
        payload (schemas.LoginRequest): Validated email and password fields.
        response (Response): FastAPI response object used to set the session cookie.
        db (Session): Per-request SQLAlchemy session injected by get_db.

    Returns:
        schemas.AuthResponse: The signed JWT token and the user's profile.

    Raises:
        HTTPException 401: If the email is not registered or the password is incorrect.
    """
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
    """
    Authenticate or register a user via a Firebase Google ID token.

    The frontend calls Firebase's signInWithPopup(GoogleAuthProvider), which returns
    a short-lived Google ID token. This endpoint verifies that token against Google's
    public keys via the Firebase Admin SDK, then upserts the user in PostgreSQL and
    issues a MARKA session JWT.

    Args:
        payload (schemas.GoogleLoginRequest): Contains the Firebase Google ID token
            in either "idToken" or "id_token" field name.
        response (Response): FastAPI response object used to set the session cookie.
        db (Session): Per-request SQLAlchemy session injected by get_db.

    Returns:
        schemas.AuthResponse: The signed JWT token and the user's profile.

    Raises:
        HTTPException 503: If Firebase Admin SDK credentials are not configured.
        HTTPException 401: If the Google ID token is invalid or expired.
    """
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
    """
    Return the profile of the currently authenticated user.

    Accepts the session token from either the Authorization header (Bearer scheme)
    or the HttpOnly access_token cookie. The cookie takes precedence when both
    are present, supporting browser-based and programmatic clients simultaneously.

    Args:
        authorization (str | None): Value of the Authorization header, injected by
            the get_bearer_token dependency.
        access_token (str | None): Value of the access_token cookie, injected by
            the get_auth_cookie dependency.
        db (Session): Per-request SQLAlchemy session injected by get_db.

    Returns:
        schemas.UserOut: The authenticated user's id, name, email, and created_at.

    Raises:
        HTTPException 401: If no valid token is present or the user no longer exists.
    """
    user = auth_service.get_current_user(
        db=db, authorization=authorization, access_token=access_token
    )
    return user


@router.post("/logout")
def logout(response: Response) -> dict[str, bool]:
    """
    Invalidate the current session by deleting the access_token cookie.

    The MARKA JWT has no server-side revocation list; expiry is enforced by the
    exp claim in the token itself. Deleting the cookie is sufficient to log out
    browser clients. Programmatic clients that stored the token in memory must
    discard it themselves.

    Args:
        response (Response): FastAPI response object used to delete the cookie.

    Returns:
        dict[str, bool]: {"logged_out": True} confirming the cookie was cleared.
    """
    response.delete_cookie(key="access_token", path="/")
    return {"logged_out": True}
