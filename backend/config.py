import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


def _load_env_file() -> None:
    env_path = Path.cwd() / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ[key] = value


@dataclass(frozen=True)
class Settings:
    database_url: str
    ollama_base_url: str
    ollama_model: str
    llm_provider: str
    groq_api_key: str
    groq_model: str
    groq_base_url: str
    embedding_model: str
    auth_secret: str
    allowed_origins: str
    ocr_fallback_enabled: bool
    ocr_max_pages: int
    environment: str
    firebase_project_id: str
    firebase_client_email: str
    firebase_private_key: str
    firebase_service_account_json: str
    firebase_service_account_key_path: str
    enable_mcp: bool


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _default_sqlite_url() -> str:
    return f"sqlite:///{(Path.home() / '.codex' / 'memories' / 'ai-multi-agent-research-assistant' / 'app.db').as_posix()}"


def _resolve_database_url() -> str:
    raw = os.getenv("DATABASE_URL", _default_sqlite_url()).strip()
    if raw == "sqlite:///./app.db":
        return _default_sqlite_url()
    return raw


@lru_cache
def get_settings() -> Settings:
    _load_env_file()
    return Settings(
        database_url=_resolve_database_url(),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        ollama_model=os.getenv("OLLAMA_MODEL", "llama3"),
        llm_provider=os.getenv("LLM_PROVIDER", "groq").strip().lower(),
        groq_api_key=os.getenv("GROQ_API_KEY", "").strip(),
        groq_model=os.getenv("GROQ_MODEL", "llama-3.1-8b-instant").strip(),
        groq_base_url=os.getenv(
            "GROQ_BASE_URL", "https://api.groq.com/openai/v1/chat/completions"
        ).strip(),
        embedding_model=os.getenv(
            "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
        ),
        auth_secret=os.getenv(
            "AUTH_SECRET", "local-dev-secret-change-before-production"
        ),
        allowed_origins=os.getenv("ALLOWED_ORIGINS", "http://localhost:3000"),
        ocr_fallback_enabled=_get_bool("OCR_FALLBACK_ENABLED", True),
        ocr_max_pages=max(1, int(os.getenv("OCR_MAX_PAGES", "20"))),
        environment=os.getenv("ENVIRONMENT", "development").strip().lower(),
        firebase_project_id=os.getenv(
            "FIREBASE_PROJECT_ID", os.getenv("NEXT_PUBLIC_FIREBASE_PROJECT_ID", "")
        ).strip(),
        firebase_client_email=os.getenv("FIREBASE_CLIENT_EMAIL", "").strip(),
        firebase_private_key=os.getenv("FIREBASE_PRIVATE_KEY", "")
        .strip()
        .replace("\\n", "\n"),
        firebase_service_account_json=os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip(),
        firebase_service_account_key_path=os.getenv(
            "FIREBASE_SERVICE_ACCOUNT_KEY_PATH", ""
        ).strip(),
        enable_mcp=_get_bool("ENABLE_MCP", False),
    )
