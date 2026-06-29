# auth_service.py
# Authentication service for the MARKA platform.
# Handles user registration, email/password login, Google OAuth via Firebase,
# custom JWT creation and verification (HMAC-SHA256), and cookie/header token
# extraction. Integrates with FastAPI's dependency injection system.

# Standard library: JWT encoding, password hashing, HMAC signing, time-based expiry
import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from pathlib import Path

# FastAPI dependency utilities for reading auth tokens from headers and cookies
from fastapi import Cookie, Header, HTTPException
# Firebase Admin SDK for Google ID token verification
import firebase_admin
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials
# SQLAlchemy session for all PostgreSQL user operations
from sqlalchemy.orm import Session

# ORM models for the PostgreSQL users table
from backend import models
# Application settings (auth secret, Firebase credentials, environment flag)
from backend.config import get_settings

logger = logging.getLogger(__name__)


def _urlsafe_encode(raw: bytes) -> str:
    """
    Base64url-encode bytes without padding characters.

    Padding is stripped because MARKA's custom JWT format uses the dot-separated
    payload.signature structure rather than the standard three-part header.payload.signature
    format, and padding characters are not needed for the binary token comparison.

    Args:
        raw (bytes): Bytes to encode.

    Returns:
        str: URL-safe base64 string without trailing "=" padding.
    """
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _urlsafe_decode(value: str) -> bytes:
    """
    Decode a base64url string that may be missing its padding characters.

    Standard base64 requires padding to a multiple of 4 characters; JWT libraries
    often strip it. This restores the necessary padding before decoding.

    Args:
        value (str): URL-safe base64 string, with or without trailing "=" padding.

    Returns:
        bytes: Decoded raw bytes.
    """
    # Calculate the number of missing "=" characters and append them
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _decode_unverified_jwt_payload(token: str) -> dict[str, object]:
    """
    Extract the payload from a Firebase JWT without verifying the signature.

    Used only for diagnostic logging when Firebase token verification fails,
    to log which project/audience/subject was present in the token so the
    misconfiguration can be identified without exposing the raw token.

    Args:
        token (str): A Firebase Google ID token string.

    Returns:
        dict[str, object]: The decoded payload dict, or an empty dict if decoding fails.
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return {}
        return json.loads(_urlsafe_decode(parts[1]).decode("utf-8"))
    except Exception:
        return {}


class AuthService:
    """
    Central authentication service integrating email/password auth, Google OAuth,
    and custom JWT session management.

    Firebase Integration:
        Firebase Admin SDK is initialized from one of three credential sources
        (JSON string, file path, or individual environment variables). Once the
        admin app is initialized, it is used to verify Google ID tokens issued
        by the Firebase Web SDK on the frontend.

    JWT Design:
        MARKA uses a custom two-part JWT (payload.signature) rather than the
        standard three-part format to keep the implementation dependency-free.
        Tokens are signed with HMAC-SHA256 using the AUTH_SECRET environment
        variable and expire after 7 days.

    Password Hashing:
        Passwords are hashed with PBKDF2-SHA256 using 100,000 iterations and
        a cryptographically random 16-byte salt. The stored hash format is:
        "{hex_salt}${hex_digest}", which embeds the salt for verification.

    Attributes:
        settings: Parsed application settings.
        _firebase_app: Initialized Firebase Admin app instance, or None if Firebase
            credentials were not configured.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        # Initialize Firebase once at service construction time; subsequent instances
        # reuse the already-initialized app via firebase_admin._apps check
        self._firebase_app = self._initialize_firebase()

    def _initialize_firebase(self):
        """
        Initialize the Firebase Admin SDK from the first available credential source.

        Tries three credential sources in priority order:
        1. FIREBASE_SERVICE_ACCOUNT_JSON: Full service account JSON as a string.
        2. FIREBASE_SERVICE_ACCOUNT_KEY_PATH: Path to a service account JSON file.
        3. Individual env vars: FIREBASE_PROJECT_ID, FIREBASE_CLIENT_EMAIL, FIREBASE_PRIVATE_KEY.

        Returns None (instead of raising) if no credentials are configured, so the
        application starts normally and returns a 503 only when Google sign-in is
        actually attempted.

        Returns:
            firebase_admin.App | None: Initialized Firebase app, or None if credentials
            are absent or initialization fails.
        """
        # Reuse an existing app if Firebase was already initialized in this process
        if firebase_admin._apps:
            return firebase_admin.get_app()

        service_account_json = self.settings.firebase_service_account_json
        if service_account_json:
            try:
                service_account_info = json.loads(service_account_json)
                if "private_key" in service_account_info:
                    # Replace escaped newlines in the private key when loaded from a JSON string
                    service_account_info["private_key"] = service_account_info[
                        "private_key"
                    ].replace("\\n", "\n")
                cert = credentials.Certificate(service_account_info)
                return firebase_admin.initialize_app(cert)
            except Exception:
                logger.exception(
                    "Failed to initialize Firebase Admin from FIREBASE_SERVICE_ACCOUNT_JSON."
                )
                return None

        service_account_key_path = self.settings.firebase_service_account_key_path
        if service_account_key_path:
            service_account_path = Path(service_account_key_path).expanduser()
            # Resolve relative paths against the server's working directory
            if not service_account_path.is_absolute():
                service_account_path = (Path.cwd() / service_account_path).resolve()
            if not service_account_path.exists():
                logger.warning(
                    "Firebase service account file was not found at %s.", service_account_path
                )
                return None

            try:
                cert = credentials.Certificate(str(service_account_path))
                return firebase_admin.initialize_app(cert)
            except Exception:
                logger.exception(
                    "Failed to initialize Firebase Admin from service account file."
                )
                return None

        if not (
            self.settings.firebase_project_id
            and self.settings.firebase_client_email
            and self.settings.firebase_private_key
        ):
            # No Firebase credentials of any kind: Google sign-in will be unavailable
            return None

        try:
            cert = credentials.Certificate(
                {
                    "type": "service_account",
                    "project_id": self.settings.firebase_project_id,
                    "client_email": self.settings.firebase_client_email,
                    "private_key": self.settings.firebase_private_key,
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            )
            return firebase_admin.initialize_app(cert)
        except Exception:
            logger.exception("Failed to initialize Firebase Admin from inline env credentials.")
            return None

    def hash_password(self, password: str, salt: str | None = None) -> str:
        """
        Hash a password using PBKDF2-SHA256 with a random or provided salt.

        The stored format is "{hex_salt}${hex_digest}" so both components are
        available for verification without a separate salt column.

        Args:
            password (str): The plaintext password to hash.
            salt (str | None): Hex-encoded salt string. If None, a fresh 16-byte
                cryptographically random salt is generated via secrets.token_hex.

        Returns:
            str: The combined hash string in the format "{salt}${digest}".
        """
        active_salt = salt or secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), active_salt.encode("utf-8"), 100_000
        ).hex()
        return f"{active_salt}${digest}"

    def verify_password(self, password: str, password_hash: str) -> bool:
        """
        Verify a plaintext password against a stored PBKDF2-SHA256 hash.

        Uses hmac.compare_digest for the final comparison to ensure the check
        runs in constant time, preventing timing-based oracle attacks.

        Args:
            password (str): The plaintext password from the login request.
            password_hash (str): The stored hash string in "{salt}${digest}" format.

        Returns:
            bool: True if the password matches the stored hash, False otherwise.
        """
        try:
            salt, expected = password_hash.split("$", 1)
        except ValueError:
            # Malformed hash (no "$" separator): treat as non-match without raising
            return False
        actual = self.hash_password(password, salt).split("$", 1)[1]
        # Constant-time comparison prevents timing attacks from leaking hash prefix information
        return hmac.compare_digest(actual, expected)

    def create_token(self, user: models.User) -> str:
        """
        Create a custom HMAC-SHA256 signed JWT for a user session.

        Token format: base64url(payload).base64url(signature)
        Payload: {"user_id": int, "email": str, "exp": unix_timestamp}
        Token lifetime: 7 days from creation time.

        Args:
            user (models.User): The authenticated user ORM instance.

        Returns:
            str: A two-part dot-separated JWT string.
        """
        payload = {
            "user_id": user.id,
            "email": user.email,
            # Expiry is 7 days (in seconds) from the current Unix timestamp
            "exp": int(time.time()) + (7 * 24 * 60 * 60),
        }
        payload_b64 = _urlsafe_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        signature = hmac.new(
            self.settings.auth_secret.encode("utf-8"),
            payload_b64.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return f"{payload_b64}.{_urlsafe_encode(signature)}"

    def verify_token(self, token: str) -> dict:
        """
        Verify the HMAC signature and expiry of a MARKA session token.

        Recomputes the expected HMAC signature from the payload and compares it
        to the provided signature using hmac.compare_digest (constant-time) to
        prevent signature oracle attacks.

        Args:
            token (str): The two-part JWT string from the Authorization header or cookie.

        Returns:
            dict: The decoded payload dict containing user_id, email, and exp.

        Raises:
            HTTPException 401: If the token format is invalid, the signature does not
                match, or the token has expired.
        """
        try:
            payload_b64, signature_b64 = token.split(".", 1)
        except ValueError as exc:
            raise HTTPException(status_code=401, detail="Invalid authentication token.") from exc

        # Recompute the expected signature from the token's own payload
        expected_signature = hmac.new(
            self.settings.auth_secret.encode("utf-8"),
            payload_b64.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        # Constant-time comparison to prevent timing-based signature guessing
        if not hmac.compare_digest(_urlsafe_encode(expected_signature), signature_b64):
            raise HTTPException(status_code=401, detail="Invalid authentication token.")

        payload = json.loads(_urlsafe_decode(payload_b64).decode("utf-8"))
        if int(payload.get("exp", 0)) < int(time.time()):
            raise HTTPException(status_code=401, detail="Authentication token expired.")
        return payload

    def register_user(self, db: Session, name: str, email: str, password: str) -> models.User:
        """
        Create a new user account with an email/password credential.

        Email is normalized to lowercase before the uniqueness check to prevent
        duplicate accounts for the same address with different capitalization.

        Args:
            db (Session): Active SQLAlchemy session for PostgreSQL write operations.
            name (str): The user's display name (2-120 characters).
            email (str): The user's email address; stored normalized to lowercase.
            password (str): The plaintext password; hashed with PBKDF2-SHA256 before storage.

        Returns:
            models.User: The newly created and committed User ORM instance.

        Raises:
            HTTPException 409: If an account with the normalized email already exists.
        """
        normalized_email = email.strip().lower()
        existing = db.query(models.User).filter(models.User.email == normalized_email).first()
        if existing is not None:
            raise HTTPException(status_code=409, detail="An account with this email already exists.")

        user = models.User(
            name=name.strip(),
            email=normalized_email,
            password_hash=self.hash_password(password),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def login_user(self, db: Session, email: str, password: str) -> models.User:
        """
        Authenticate a user with email and password.

        The "user not found" and "wrong password" cases return the same 401 response
        to prevent user enumeration attacks via timing or error message differences.

        Args:
            db (Session): Active SQLAlchemy session for the user lookup query.
            email (str): The submitted email address, normalized before lookup.
            password (str): The submitted plaintext password, verified against the stored hash.

        Returns:
            models.User: The authenticated User ORM instance.

        Raises:
            HTTPException 401: If the email is not registered or the password is incorrect.
        """
        normalized_email = email.strip().lower()
        user = db.query(models.User).filter(models.User.email == normalized_email).first()
        if user is None or not self.verify_password(password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid email or password.")
        return user

    def login_with_google(self, db: Session, id_token: str) -> models.User:
        """
        Authenticate or register a user via a Firebase Google ID token.

        Verifies the ID token using the Firebase Admin SDK, which validates the
        token's signature against Google's public keys and checks the audience
        (Firebase project ID) and expiry. On success, upserts the user in PostgreSQL.

        Args:
            db (Session): Active SQLAlchemy session for the user upsert operation.
            id_token (str): The Firebase Google ID token from the frontend's
                signInWithPopup(GoogleAuthProvider) call.

        Returns:
            models.User: The existing or newly created User ORM instance.

        Raises:
            HTTPException 503: If the Firebase Admin SDK was not initialized (credentials missing).
            HTTPException 401: If the Google ID token is invalid, expired, or from the wrong project.
            HTTPException 400: If the verified token does not contain an email address.
        """
        if self._firebase_app is None:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Google sign-in is not configured on the server. "
                    "Set FIREBASE_SERVICE_ACCOUNT_JSON, FIREBASE_SERVICE_ACCOUNT_KEY_PATH, "
                    "or the FIREBASE_PROJECT_ID, FIREBASE_CLIENT_EMAIL, and "
                    "FIREBASE_PRIVATE_KEY env vars."
                ),
            )

        try:
            # clock_skew_seconds=10 tolerates minor clock drift between the client and server
            decoded = firebase_auth.verify_id_token(
                id_token,
                app=self._firebase_app,
                clock_skew_seconds=10,
            )
        except Exception as exc:
            # Decode the payload without verification to log diagnostic fields
            # (aud, iss, sub, email) that help identify the misconfiguration source
            payload = _decode_unverified_jwt_payload(id_token)
            logger.warning(
                "Firebase ID token verification failed: %s: %s | aud=%s iss=%s sub=%s email=%s",
                type(exc).__name__,
                exc,
                payload.get("aud"),
                payload.get("iss"),
                payload.get("sub"),
                payload.get("email"),
            )
            raise HTTPException(status_code=401, detail="Invalid Google sign-in token.") from exc

        email = str(decoded.get("email", "")).strip().lower()
        if not email:
            raise HTTPException(status_code=400, detail="Google account did not provide an email.")

        # Use the display name from the Google token, or fall back to the email prefix
        name = str(decoded.get("name") or email.split("@", 1)[0]).strip()
        user = db.query(models.User).filter(models.User.email == email).first()
        if user is None:
            # First Google sign-in: create a new user with an empty password_hash
            # since OAuth users authenticate through Google, not a local password
            user = models.User(name=name[:120], email=email, password_hash="")
            db.add(user)
            db.commit()
            db.refresh(user)
            return user

        # Update the display name if the Google profile name has changed since last login
        updated = False
        if name and user.name != name[:120]:
            user.name = name[:120]
            updated = True
        if updated:
            db.commit()
            db.refresh(user)
        return user

    def extract_token(self, authorization: str | None, access_token: str | None) -> str:
        """
        Extract the bearer token from either an Authorization header or a cookie.

        The cookie takes precedence over the header to support browser-based clients
        that send the token automatically via the HttpOnly cookie set on login.

        Args:
            authorization (str | None): Value of the "Authorization" request header,
                expected in "Bearer <token>" format.
            access_token (str | None): Value of the "access_token" cookie.

        Returns:
            str: The extracted raw token string.

        Raises:
            HTTPException 401: If neither the cookie nor the header contains a token.
        """
        if access_token:
            return access_token
        if authorization and authorization.startswith("Bearer "):
            return authorization.split(" ", 1)[1].strip()
        raise HTTPException(status_code=401, detail="Authentication required.")

    def get_current_user(
        self, db: Session, authorization: str | None, access_token: str | None
    ) -> models.User:
        """
        Resolve the currently authenticated user from a request's auth credentials.

        This is the primary FastAPI dependency for protected endpoints. It extracts
        the token, verifies its signature and expiry, then loads the user from
        PostgreSQL to confirm the account still exists.

        Args:
            db (Session): Active SQLAlchemy session for the user lookup.
            authorization (str | None): Authorization header value.
            access_token (str | None): access_token cookie value.

        Returns:
            models.User: The authenticated User ORM instance.

        Raises:
            HTTPException 401: If the token is missing, invalid, expired, or the
                corresponding user no longer exists in the database.
        """
        token = self.extract_token(authorization, access_token)
        payload = self.verify_token(token)
        user = db.query(models.User).filter(models.User.id == int(payload["user_id"])).first()
        if user is None:
            raise HTTPException(status_code=401, detail="User session is no longer valid.")
        return user


def get_bearer_token(authorization: str | None = Header(default=None)) -> str | None:
    """
    FastAPI dependency that extracts the Authorization header value.

    Args:
        authorization (str | None): Injected by FastAPI from the Authorization header.

    Returns:
        str | None: The raw header value, or None if the header was not sent.
    """
    return authorization


def get_auth_cookie(access_token: str | None = Cookie(default=None)) -> str | None:
    """
    FastAPI dependency that extracts the access_token cookie value.

    Args:
        access_token (str | None): Injected by FastAPI from the access_token cookie.

    Returns:
        str | None: The raw cookie value, or None if the cookie was not present.
    """
    return access_token
