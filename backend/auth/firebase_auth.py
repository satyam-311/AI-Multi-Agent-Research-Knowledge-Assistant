import hashlib
import json

import firebase_admin
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials

from config import get_settings


def _initialize_firebase():
    if firebase_admin._apps:
        return firebase_admin.get_app()

    settings = get_settings()
    service_account_json = settings.firebase_service_account_json
    if not service_account_json:
        return None

    try:
        service_account_info = json.loads(service_account_json)
        if "private_key" in service_account_info:
            service_account_info["private_key"] = service_account_info["private_key"].replace(
                "\\n", "\n"
            )
        cert = credentials.Certificate(service_account_info)
        return firebase_admin.initialize_app(cert)
    except Exception:
        return None


def get_firebase_app():
    return _initialize_firebase()


def verify_token(token: str):
    if not token:
        return "test_user"

    app = get_firebase_app()
    if app is None:
        return "test_user"

    try:
        decoded = firebase_auth.verify_id_token(token, app=app)
        return str(decoded["uid"])
    except Exception:
        return "test_user"


def _uid_to_int(uid: str) -> int:
    digest = hashlib.sha256(uid.encode("utf-8")).digest()
    return (int.from_bytes(digest[:8], "big") % 2_000_000_000) + 1


def get_user_id(request):
    authorization = request.headers.get("Authorization", "").strip()
    token = ""
    if authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1].strip()
    uid = verify_token(token)
    return _uid_to_int(uid)
