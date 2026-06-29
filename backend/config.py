# config.py
# Application settings loader for the MARKA backend.
# Parses environment variables and .env file values into a frozen dataclass
# that is cached for the process lifetime. All other modules call get_settings()
# to read configuration rather than accessing os.environ directly.

import os
from dataclasses import dataclass
# lru_cache ensures the .env file is parsed exactly once per process,
# not on every configuration access across multiple requests
from functools import lru_cache
from pathlib import Path


def _load_env_file() -> None:
    """
    Parse a .env file in the current working directory and populate os.environ.

    Only runs if a .env file exists. Values are stripped of surrounding quotes
    to handle both quoted ("value") and unquoted (value) formats. Existing
    environment variables are overwritten so the .env file takes precedence over
    variables inherited from the shell.

    Returns:
        None
    """
    env_path = Path.cwd() / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        # Skip blank lines and comment lines (# prefix)
        if not line or line.startswith("#") or "=" not in line:
            continue

        # Split on the first "=" only to handle values that contain "=" (e.g. base64 strings)
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ[key] = value


@dataclass(frozen=True)
class Settings:
    """
    Immutable typed container for all application configuration values.

    Frozen to prevent accidental mutation after initialization. All fields are
    strings or primitives so they can be safely shared across threads without
    synchronization.

    Attributes:
        database_url (str): SQLAlchemy database connection string. Defaults to
            SQLite in the user home directory for local development.
        chroma_persist_directory (str): Filesystem path where ChromaDB stores its
            vector index. Defaults to a platform-appropriate app data directory.
        ollama_base_url (str): Base URL of the local Ollama server.
        ollama_model (str): Name of the Ollama model to use (e.g. "llama3").
        llm_provider (str): Which LLM backend to use: "groq" or "ollama".
        groq_api_key (str): API key for the Groq cloud service.
        groq_model (str): Groq model identifier (e.g. "llama-3.1-8b-instant").
        groq_base_url (str): Full URL for the Groq chat completions endpoint.
        embedding_model (str): HuggingFace model ID for sentence-transformer embeddings.
        auth_secret (str): HMAC secret for signing and verifying session JWTs.
            Must be changed from the default before production deployment.
        allowed_origins (str): Comma-separated list of CORS-allowed origins.
        ocr_fallback_enabled (bool): Whether to attempt Tesseract OCR when pypdf
            returns no text.
        ocr_max_pages (int): Maximum number of pages to OCR per document.
        environment (str): Deployment environment ("development" or "production").
            Controls whether session cookies are set with the Secure flag.
        firebase_project_id (str): Firebase project ID for Google OAuth token verification.
        firebase_client_email (str): Firebase service account client email.
        firebase_private_key (str): Firebase service account RSA private key.
        firebase_service_account_json (str): Full service account JSON as a single string.
        firebase_service_account_key_path (str): Filesystem path to service account JSON file.
        tavily_api_key (str): API key for the Tavily web search service.
    """

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
    environment: str
    firebase_project_id: str
    firebase_client_email: str
    firebase_private_key: str
    firebase_service_account_json: str
    firebase_service_account_key_path: str
    tavily_api_key: str


def _get_bool(name: str, default: bool) -> bool:
    """
    Read an environment variable as a boolean with a fallback default.

    Accepts "1", "true", "yes", "on" (case-insensitive) as truthy values;
    all other non-empty strings are treated as False.

    Args:
        name (str): Environment variable name.
        default (bool): Value to return if the variable is not set.

    Returns:
        bool: Parsed boolean value.
    """
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _default_chroma_directory() -> str:
    """
    Compute the default ChromaDB persistence path for the current platform.

    Uses LOCALAPPDATA on Windows (the standard application data location),
    or the home directory on macOS and Linux.

    Returns:
        str: Absolute path string to the default ChromaDB directory.
    """
    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        return str(Path(local_app_data) / "ai-multi-agent-research-assistant" / "chroma")
    return str(Path.home() / ".ai-multi-agent-research-assistant" / "chroma")


def _default_sqlite_url() -> str:
    """
    Compute the default SQLite database URL for local development.

    Placed in the user's home directory to avoid permission issues when running
    without administrator privileges.

    Returns:
        str: SQLAlchemy-compatible sqlite:/// URL string.
    """
    return f"sqlite:///{(Path.home() / '.codex' / 'memories' / 'ai-multi-agent-research-assistant' / 'app.db').as_posix()}"


def _resolve_database_url() -> str:
    """
    Resolve the DATABASE_URL with a special case for the legacy relative SQLite path.

    The value "sqlite:///./app.db" (relative path) is replaced with the absolute
    default path to prevent path resolution differences between launch directories.

    Returns:
        str: The final database URL to use for SQLAlchemy engine creation.
    """
    raw = os.getenv("DATABASE_URL", _default_sqlite_url()).strip()
    # Normalize the legacy relative SQLite path to an absolute one
    if raw == "sqlite:///./app.db":
        return _default_sqlite_url()
    return raw


@lru_cache
def get_settings() -> Settings:
    """
    Load, parse, and cache all application configuration as an immutable Settings object.

    Called at module import time by most backend modules. The lru_cache ensures
    the .env file is read and parsed exactly once per process, regardless of how
    many modules call get_settings().

    Returns:
        Settings: Frozen dataclass instance containing all resolved configuration values.
    """
    _load_env_file()
    return Settings(
        database_url=_resolve_database_url(),
        chroma_persist_directory=os.getenv(
            "CHROMA_PERSIST_DIRECTORY", _default_chroma_directory()
        ),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        ollama_model=os.getenv("OLLAMA_MODEL", "llama3"),
        # Normalize to lowercase so provider comparisons are case-insensitive
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
        # Firebase project ID can also be set via the frontend's NEXT_PUBLIC_ variable
        # as a fallback for development environments that share a single .env file
        firebase_project_id=os.getenv(
            "FIREBASE_PROJECT_ID", os.getenv("NEXT_PUBLIC_FIREBASE_PROJECT_ID", "")
        ).strip(),
        firebase_client_email=os.getenv("FIREBASE_CLIENT_EMAIL", "").strip(),
        # Replace literal "\n" escape sequences with actual newlines in the private key,
        # which is necessary when the key is stored as a single-line string in .env
        firebase_private_key=os.getenv("FIREBASE_PRIVATE_KEY", "")
        .strip()
        .replace("\\n", "\n"),
        firebase_service_account_json=os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip(),
        firebase_service_account_key_path=os.getenv(
            "FIREBASE_SERVICE_ACCOUNT_KEY_PATH", ""
        ).strip(),
        tavily_api_key=os.getenv("TAVILY_API_KEY", "").strip(),
    )
