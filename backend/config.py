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
    chroma_persist_directory: str
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


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _default_chroma_directory() -> str:
    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        return str(Path(local_app_data) / "ai-multi-agent-research-assistant" / "chroma")
    return str(Path.home() / ".ai-multi-agent-research-assistant" / "chroma")


def _default_sqlite_url() -> str:
    return "sqlite:///C:/Users/Satyam Mishra/.codex/memories/ai-multi-agent-research-assistant/app.db"


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
        chroma_persist_directory=os.getenv(
            "CHROMA_PERSIST_DIRECTORY", _default_chroma_directory()
        ),
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
    )
