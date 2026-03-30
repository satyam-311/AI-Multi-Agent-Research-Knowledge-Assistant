import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from pathlib import Path

from fastapi import Cookie, Header, HTTPException
import firebase_admin
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials
from sqlalchemy.orm import Session

from backend import models
from backend.config import get_settings

logger = logging.getLogger(__name__)


def _urlsafe_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _urlsafe_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _decode_unverified_jwt_payload(token: str) -> dict[str, object]:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return {}
        return json.loads(_urlsafe_decode(parts[1]).decode("utf-8"))
    except Exception:
        return {}


class AuthService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._firebase_app = self._initialize_firebase()

    def _initialize_firebase(self):
        if firebase_admin._apps:
            return firebase_admin.get_app()

        service_account_json = self.settings.firebase_service_account_json
        if service_account_json:
            try:
                service_account_info = json.loads(service_account_json)
                if "private_key" in service_account_info:
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
        active_salt = salt or secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), active_salt.encode("utf-8"), 100_000
        ).hex()
        return f"{active_salt}${digest}"

    def verify_password(self, password: str, password_hash: str) -> bool:
        try:
            salt, expected = password_hash.split("$", 1)
        except ValueError:
            return False
        actual = self.hash_password(password, salt).split("$", 1)[1]
        return hmac.compare_digest(actual, expected)

    def create_token(self, user: models.User) -> str:
        payload = {
            "user_id": user.id,
            "email": user.email,
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
        try:
            payload_b64, signature_b64 = token.split(".", 1)
        except ValueError as exc:
            raise HTTPException(status_code=401, detail="Invalid authentication token.") from exc

        expected_signature = hmac.new(
            self.settings.auth_secret.encode("utf-8"),
            payload_b64.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(_urlsafe_encode(expected_signature), signature_b64):
            raise HTTPException(status_code=401, detail="Invalid authentication token.")

        payload = json.loads(_urlsafe_decode(payload_b64).decode("utf-8"))
        if int(payload.get("exp", 0)) < int(time.time()):
            raise HTTPException(status_code=401, detail="Authentication token expired.")
        return payload

    def register_user(self, db: Session, name: str, email: str, password: str) -> models.User:
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
        normalized_email = email.strip().lower()
        user = db.query(models.User).filter(models.User.email == normalized_email).first()
        if user is None or not self.verify_password(password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid email or password.")
        return user

    def login_with_google(self, db: Session, id_token: str) -> models.User:
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
            decoded = firebase_auth.verify_id_token(
                id_token,
                app=self._firebase_app,
                clock_skew_seconds=10,
            )
        except Exception as exc:
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

        name = str(decoded.get("name") or email.split("@", 1)[0]).strip()
        user = db.query(models.User).filter(models.User.email == email).first()
        if user is None:
            user = models.User(name=name[:120], email=email, password_hash="")
            db.add(user)
            db.commit()
            db.refresh(user)
            return user

        updated = False
        if name and user.name != name[:120]:
            user.name = name[:120]
            updated = True
        if updated:
            db.commit()
            db.refresh(user)
        return user

    def extract_token(self, authorization: str | None, access_token: str | None) -> str:
        if access_token:
            return access_token
        if authorization and authorization.startswith("Bearer "):
            return authorization.split(" ", 1)[1].strip()
        raise HTTPException(status_code=401, detail="Authentication required.")

    def get_current_user(
        self, db: Session, authorization: str | None, access_token: str | None
    ) -> models.User:
        token = self.extract_token(authorization, access_token)
        payload = self.verify_token(token)
        user = db.query(models.User).filter(models.User.id == int(payload["user_id"])).first()
        if user is None:
            raise HTTPException(status_code=401, detail="User session is no longer valid.")
        return user


def get_bearer_token(authorization: str | None = Header(default=None)) -> str | None:
    return authorization


def get_auth_cookie(access_token: str | None = Cookie(default=None)) -> str | None:
    return access_token
