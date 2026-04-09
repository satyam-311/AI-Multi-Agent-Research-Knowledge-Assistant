from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from backend.auth.jwt_handler import decode_access_token
from backend.auth.models import AuthUser
from backend.database import SessionLocal


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if request.method.upper() == "OPTIONS":
            return await call_next(request)

        if path in {"/health", "/openapi.json", "/docs", "/redoc"}:
            return await call_next(request)

        if path == "/auth" or path.startswith("/auth/"):
            return await call_next(request)

        authorization = request.headers.get("Authorization", "").strip()
        if not authorization.lower().startswith("bearer "):
            return JSONResponse(status_code=401, content={"detail": "Authentication required."})

        token = authorization.split(" ", 1)[1].strip()
        try:
            payload = decode_access_token(token)
        except Exception as exc:
            detail = getattr(exc, "detail", "Invalid authentication token.")
            status_code = getattr(exc, "status_code", 401)
            return JSONResponse(status_code=status_code, content={"detail": detail})

        db = SessionLocal()
        try:
            user = db.query(AuthUser).filter(AuthUser.id == int(payload["sub"])).first()
            if user is None or not user.is_verified:
                return JSONResponse(status_code=401, content={"detail": "User session is invalid."})
            db.expunge(user)
            request.state.user = user
        finally:
            db.close()

        return await call_next(request)
