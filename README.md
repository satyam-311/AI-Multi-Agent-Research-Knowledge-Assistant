# AI Multi-Agent Research Knowledge Assistant

> A full-stack research assistant that lets you upload PDF documents and ask questions against them using a sophisticated multi-agent Retrieval-Augmented Generation (RAG) pipeline, enriched with live Arxiv paper search and web search capabilities.

---

## Features

- **PDF Document Ingestion** — Upload PDFs, automatically extract text (with OCR fallback for scanned documents), chunk, embed, and index into a vector store
- **Multi-Agent RAG Pipeline** — Orchestrated pipeline of specialized agents: retrieval, answer generation, Arxiv search, and web search
- **Semantic Vector Search** — ChromaDB-powered similarity search using 384-dimensional sentence embeddings
- **Arxiv Integration** — Automatically searches academic papers when research-oriented queries are detected
- **Web Search Augmentation** — Tavily API integration for real-time web context when document confidence is low
- **Dual LLM Support** — Choose between Groq API (cloud) or Ollama (local) for answer generation
- **Firebase Authentication** — Email/password and Google OAuth sign-in
- **Custom JWT Sessions** — Stateless HMAC-SHA256 signed tokens with HttpOnly cookie support
- **Chat History** — Per-user, per-document conversation tracking stored in SQLite/PostgreSQL
- **OCR Fallback** — Automatic OCR using PyMuPDF + Tesseract for image-based PDFs
- **Dark/Light Theme** — Toggleable theme with Tailwind CSS
- **Responsive UI** — Next.js 16 + React 19 frontend with sidebar navigation

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | Next.js 16, React 19, TypeScript, Tailwind CSS, Lucide React |
| **Backend** | FastAPI, SQLAlchemy 2.0, Pydantic v2, Uvicorn |
| **Database** | SQLite (development) / PostgreSQL (production-ready) |
| **Vector Store** | ChromaDB (local persistent) |
| **Embeddings** | `sentence-transformers/all-MiniLM-L6-v2` (384-dim, HuggingFace) |
| **LLM Providers** | Groq API (`llama-3.1-8b-instant`) or local Ollama (`llama3`) |
| **Authentication** | Firebase Admin SDK (backend) + Firebase Web SDK (frontend) |
| **Web Search** | Tavily API |
| **Paper Search** | Arxiv API (via `arxiv` Python client) |
| **PDF Processing** | pypdf (text extraction) + PyMuPDF + pytesseract (OCR) |
| **HTTP Client** | httpx (async, backend) |

---

## Project Architecture

The system is composed of a Next.js frontend, a FastAPI backend with a multi-agent orchestration layer, and two persistence layers (SQLite for relational data, ChromaDB for vector embeddings).

```mermaid
graph TB
    subgraph Frontend ["Frontend (Next.js 16)"]
        UI[React UI / Pages]
        AuthCtx[Auth Context / Firebase SDK]
        APIClient[API Client lib/api.ts]
    end

    subgraph Backend ["Backend (FastAPI)"]
        AuthRoutes[/auth routes/]
        RAGRoutes[/rag routes/]
        ChatRoutes[/chat routes/]

        subgraph Orchestrator ["Multi-Agent Orchestrator"]
            Orch[orchestrator.py]
            RAGAgent[RAG Agent]
            RetAgent[Retrieval Agent]
            EmbAgent[Embedding Agent]
            DocAgent[Document Processing Agent]
            AnsAgent[Answer Generation Agent]
            ArxivAgent[Arxiv Agent]
            DDGAgent[Web Search Agent]
        end

        AuthSvc[Auth Service / JWT + Firebase]
    end

    subgraph Persistence ["Persistence"]
        SQLite[(SQLite / PostgreSQL)]
        Chroma[(ChromaDB Vector Store)]
    end

    subgraph External ["External APIs"]
        Groq[Groq API]
        Ollama[Ollama Local]
        Firebase[Firebase Auth]
        ArxivAPI[Arxiv API]
        TavilyAPI[Tavily API]
    end

    UI --> AuthCtx
    UI --> APIClient
    APIClient --> AuthRoutes
    APIClient --> RAGRoutes
    APIClient --> ChatRoutes
    AuthRoutes --> AuthSvc
    AuthSvc --> Firebase
    AuthSvc --> SQLite
    RAGRoutes --> DocAgent
    RAGRoutes --> EmbAgent
    EmbAgent --> Chroma
    ChatRoutes --> Orch
    Orch --> RAGAgent
    RAGAgent --> RetAgent
    RetAgent --> Chroma
    Orch --> AnsAgent
    AnsAgent --> Groq
    AnsAgent --> Ollama
    Orch --> ArxivAgent
    ArxivAgent --> ArxivAPI
    Orch --> DDGAgent
    DDGAgent --> TavilyAPI
    Orch --> SQLite
    RAGRoutes --> SQLite
```

---

## Folder Structure

```
AI-Multi-Agent-Research-Knowledge-Assistant/
├── backend/
│   ├── agents/                           # Multi-agent orchestration layer
│   │   ├── answer_generation_agent.py   # LLM answer synthesis (Groq / Ollama)
│   │   ├── arxiv_agent.py               # Arxiv paper search with caching & rate-limiting
│   │   ├── ddg_agent.py                 # Tavily web search with retry logic
│   │   ├── document_processing_agent.py # PDF text extraction + chunking + OCR fallback
│   │   ├── embedding_agent.py           # Chunk embedding and ChromaDB indexing
│   │   ├── orchestrator.py              # Main multi-agent coordinator and router
│   │   ├── rag_agent.py                 # RAG context collection with similarity scoring
│   │   ├── retrieval_agent.py           # Vector similarity search interface
│   │   └── __init__.py
│   ├── routes/
│   │   ├── auth.py                      # Register, login, Google OAuth, /me, logout
│   │   ├── chat.py                      # Ask question + fetch chat history
│   │   ├── rag.py                       # Upload, list, delete documents; ask; history
│   │   ├── health.py                    # Liveness health check
│   │   └── __init__.py                  # Router registration (/ and /api/ prefixes)
│   ├── services/
│   │   ├── auth_service.py              # JWT creation/verification + Firebase token verification
│   │   ├── embedding_backend.py         # Embedding model loader with fallback
│   │   ├── pdf_service.py               # OCR service (PyMuPDF + Tesseract)
│   │   ├── rag_service.py               # RAG service wrapper
│   │   ├── source_utils.py              # Source normalization utilities
│   │   ├── vector_store.py              # ChromaDB client interface
│   │   └── __init__.py
│   ├── config.py                        # Settings management (pydantic + .env parsing)
│   ├── database.py                      # SQLAlchemy engine, session, auto-migrations
│   ├── models.py                        # SQLAlchemy ORM models (User, Document, ChatHistory)
│   ├── schemas.py                       # Pydantic request/response schemas
│   └── main.py                          # FastAPI app initialization, CORS, router mounting
├── frontend/
│   ├── app/
│   │   ├── (workspace)/                 # Auth-protected route group
│   │   │   ├── layout.tsx               # Workspace layout with sidebar
│   │   │   ├── chat/page.tsx            # Chat interface page
│   │   │   ├── dashboard/page.tsx       # Dashboard overview
│   │   │   ├── documents/page.tsx       # Document list and management
│   │   │   └── upload/page.tsx          # PDF upload interface
│   │   ├── login/
│   │   │   ├── page.tsx                 # Login page wrapper
│   │   │   └── login-form.tsx           # Email + Google sign-in form
│   │   ├── layout.tsx                   # Root layout with providers
│   │   ├── page.tsx                     # Landing page
│   │   └── globals.css                  # Global styles
│   ├── components/
│   │   ├── auth-guard.tsx               # Route protection HOC
│   │   ├── auth-provider.tsx            # Firebase auth context provider
│   │   ├── chat-workspace.tsx           # Main chat interface container
│   │   ├── chat-panel.tsx               # Message display panel
│   │   ├── document-upload-view.tsx     # Upload UI
│   │   ├── app-sidebar.tsx              # Navigation sidebar
│   │   ├── markdown-message.tsx         # Markdown renderer for answers
│   │   ├── theme-toggle.tsx             # Dark/light mode toggle
│   │   ├── toast-provider.tsx           # Toast notification system
│   │   └── ui/                          # Base UI components (Button, Card, Input, Badge)
│   ├── lib/
│   │   ├── api.ts                       # Typed HTTP client for all backend endpoints
│   │   ├── firebase.js                  # Firebase SDK initialization
│   │   └── utils.ts                     # Shared utility functions
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.js
│   └── .env.example
├── .env.example                         # Backend environment variable template
├── .gitignore
├── requirements.txt                     # Python dependencies
└── README.md
```

---

## Installation

### Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | 3.11+ | Backend runtime |
| Node.js | 18+ | Frontend runtime |
| npm | 9+ | Package manager |
| Tesseract OCR | 5.x | Optional, for scanned PDFs |
| Ollama | Latest | Optional, for local LLM inference |

**Install Tesseract (Windows) — optional:**
```powershell
winget install UB-Mannheim.TesseractOCR
# Default path: C:\Program Files\Tesseract-OCR\tesseract.exe
```

**Install Tesseract (macOS/Linux) — optional:**
```bash
# macOS
brew install tesseract

# Ubuntu/Debian
sudo apt-get install tesseract-ocr
```

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/AI-Multi-Agent-Research-Knowledge-Assistant.git
cd AI-Multi-Agent-Research-Knowledge-Assistant
```

### 2. Backend Setup

```powershell
# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS / Linux

# Install Python dependencies
pip install -r requirements.txt
```

### 3. Frontend Setup

```powershell
cd frontend
npm install
cd ..
```

### 4. Configure Environment Variables

```powershell
# Copy templates
Copy-Item .env.example .env
Copy-Item frontend\.env.example frontend\.env.local
```

Fill in your values — see the [Environment Variables](#environment-variables) section below.

---

## Environment Variables

### Backend (`/.env`)

| Variable | Default | Required | Description |
|---|---|---|---|
| `DATABASE_URL` | SQLite in `~/.ai-multi-agent-research-assistant/` | No | SQLAlchemy DB connection string. Use `sqlite:///./app.db` locally or a PostgreSQL URL in production |
| `CHROMA_PERSIST_DIRECTORY` | `~/.ai-multi-agent-research-assistant/chroma` | No | Local filesystem path for ChromaDB vector persistence |
| `LLM_PROVIDER` | `groq` | No | LLM backend: `groq` (cloud) or `ollama` (local) |
| `GROQ_API_KEY` | — | Yes (if using Groq) | API key from [console.groq.com](https://console.groq.com) |
| `GROQ_MODEL` | `llama-3.1-8b-instant` | No | Groq model identifier |
| `GROQ_BASE_URL` | Groq endpoint | No | Override only to proxy requests |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | No | Ollama server base URL |
| `OLLAMA_MODEL` | `llama3` | No | Ollama model name (must be pulled locally) |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | No | HuggingFace model for embeddings |
| `AUTH_SECRET` | `local-dev-secret-change-before-production` | **Yes (prod)** | HMAC secret for JWT signing — **change in production** |
| `ENVIRONMENT` | `development` | No | `development` or `production` (enables secure cookies) |
| `API_HOST` | `0.0.0.0` | No | Uvicorn bind host |
| `API_PORT` | `8000` | No | Uvicorn bind port |
| `ALLOWED_ORIGINS` | `http://localhost:3000` | No | Comma-separated CORS allowed origins |
| `OCR_FALLBACK_ENABLED` | `true` | No | Enable OCR for scanned PDFs |
| `OCR_MAX_PAGES` | `20` | No | Maximum pages to OCR per document |
| `TESSERACT_CMD` | `C:\Program Files\Tesseract-OCR\tesseract.exe` | No | Path to Tesseract binary (Windows) |
| `TAVILY_API_KEY` | — | Yes (for web search) | API key from [tavily.com](https://tavily.com) |
| `FIREBASE_PROJECT_ID` | — | Yes (for Google OAuth) | Firebase project ID |
| `FIREBASE_CLIENT_EMAIL` | — | Yes (for Google OAuth) | Firebase service account email |
| `FIREBASE_PRIVATE_KEY` | — | Yes (for Google OAuth) | Firebase private key (escape newlines as `\n`) |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | — | Alternative to above 3 | Full service account JSON as a single-line string |
| `FIREBASE_SERVICE_ACCOUNT_KEY_PATH` | — | Alternative to above | Path to service account JSON file |

> **Firebase:** Provide either `FIREBASE_SERVICE_ACCOUNT_JSON`, `FIREBASE_SERVICE_ACCOUNT_KEY_PATH`, or all three of `FIREBASE_PROJECT_ID` + `FIREBASE_CLIENT_EMAIL` + `FIREBASE_PRIVATE_KEY`.

### Frontend (`/frontend/.env.local`)

| Variable | Default | Required | Description |
|---|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | `http://127.0.0.1:8000` | No | Backend API base URL (change port if backend runs on 8001) |
| `NEXT_PUBLIC_FIREBASE_API_KEY` | — | Yes (for Google OAuth) | Firebase web API key |
| `NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN` | — | Yes (for Google OAuth) | Firebase auth domain (`<project>.firebaseapp.com`) |
| `NEXT_PUBLIC_FIREBASE_PROJECT_ID` | — | Yes (for Google OAuth) | Firebase project ID |
| `NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET` | — | No | Firebase storage bucket (not currently used) |
| `NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID` | — | No | Firebase messaging sender ID (not currently used) |
| `NEXT_PUBLIC_FIREBASE_APP_ID` | — | Yes (for Google OAuth) | Firebase app ID |

---

## Running the Project

### Start the Backend

```powershell
# From repo root with venv active
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8001
```

Interactive API docs available at: `http://127.0.0.1:8001/docs`

### Start the Frontend

```powershell
cd frontend
npm run dev
```

Frontend available at: `http://localhost:3000`

### Using Ollama (Local LLM)

```bash
# Pull the model first
ollama pull llama3

# Start Ollama server (runs automatically on most platforms)
ollama serve
```

Set `LLM_PROVIDER=ollama` in your `.env`.

---

## API Documentation

All routes are accessible under both `/` and `/api/` prefixes (e.g., `POST /auth/register` and `POST /api/auth/register` both work).

### Authentication

#### `POST /auth/register`

Register a new user with email and password.

**Request Body:**
```json
{
  "name": "Jane Doe",
  "email": "jane@example.com",
  "password": "securePassword123"
}
```

**Response `200`:**
```json
{
  "token": "<jwt>",
  "user": {
    "id": 1,
    "name": "Jane Doe",
    "email": "jane@example.com",
    "created_at": "2025-01-01T00:00:00Z"
  }
}
```

---

#### `POST /auth/login`

Authenticate an existing user.

**Request Body:**
```json
{
  "email": "jane@example.com",
  "password": "securePassword123"
}
```

**Response `200`:** Same shape as `/auth/register`.

---

#### `POST /auth/google`

Exchange a Firebase Google ID token for a backend JWT.

**Request Body:**
```json
{ "idToken": "<firebase-google-id-token>" }
```

**Response `200`:** Same shape as `/auth/register`.

---

#### `GET /auth/me`

Return the currently authenticated user.

**Headers:** `Authorization: Bearer <token>` (or `access_token` cookie)

**Response `200`:**
```json
{
  "id": 1,
  "name": "Jane Doe",
  "email": "jane@example.com",
  "created_at": "2025-01-01T00:00:00Z"
}
```

---

#### `POST /auth/logout`

Clear the session cookie.

**Response `200`:**
```json
{ "logged_out": true }
```

---

### Documents (RAG)

#### `POST /rag/upload_document`

Upload a PDF, extract text, chunk, embed, and index to ChromaDB.

**Request:** `multipart/form-data`

| Field | Type | Required | Description |
|---|---|---|---|
| `file` | File (PDF) | Yes | PDF document to upload |
| `user_id` | integer | No | User ID (can be inferred from token) |

**Response `200`:**
```json
{
  "document_id": 42,
  "user_id": 1,
  "filename": "research-paper.pdf",
  "chunks_created": 47
}
```

---

#### `GET /rag/documents?user_id={id}`

List all documents for a user.

**Response `200`:**
```json
[
  {
    "id": 42,
    "user_id": 1,
    "filename": "research-paper.pdf",
    "content_preview": "This paper presents...",
    "created_at": "2025-01-01T00:00:00Z"
  }
]
```

---

#### `DELETE /rag/documents/{document_id}?user_id={id}`

Delete a document along with its vector embeddings and chat history.

**Response `200`:**
```json
{ "document_id": 42, "deleted": true }
```

---

### Chat

#### `POST /chat`

Ask a question and receive a grounded answer with cited sources.

**Request Body:**
```json
{
  "question": "What is the proposed methodology in this paper?",
  "document_id": 42,
  "user_id": 1,
  "top_k": 4
}
```

> Omit `document_id` for a general research query (triggers Arxiv + web search agents).

**Response `200`:**
```json
{
  "user_id": 1,
  "answer": "The paper proposes a novel transformer-based approach...",
  "sources": {
    "rag": [
      {
        "type": "rag",
        "title": "research-paper.pdf",
        "summary": "The methodology involves...",
        "similarity": 0.82
      }
    ],
    "arxiv": [
      {
        "type": "arxiv",
        "title": "Attention Is All You Need",
        "pdf_url": "https://arxiv.org/pdf/1706.03762",
        "summary": "We propose a new network architecture...",
        "published_at": "2017-06-12"
      }
    ],
    "ddg": [
      {
        "type": "ddg",
        "title": "Transformer Models Explained",
        "link": "https://example.com/transformers",
        "snippet": "Transformer models use self-attention..."
      }
    ]
  }
}
```

---

#### `GET /chat/history?document_id={id}&user_id={id}&limit=50`

Retrieve chat history for a specific document.

**Response `200`:**
```json
[
  {
    "id": 7,
    "user_id": 1,
    "document_id": 42,
    "question": "What is the methodology?",
    "answer": "The paper proposes...",
    "sources": [...],
    "created_at": "2025-01-01T00:05:00Z"
  }
]
```

---

#### `GET /health`

Basic liveness check.

**Response `200`:**
```json
{ "status": "ok", "message": "API is running" }
```

---

## Machine Learning Pipeline

### Document Ingestion Flow

```mermaid
flowchart TD
    A[User uploads PDF] --> B[DocumentProcessingAgent]
    B --> C{Text extraction via pypdf}
    C -->|Success| D[Raw text]
    C -->|Empty / failed| E{OCR enabled?}
    E -->|Yes| F[PyMuPDF: render pages as images]
    F --> G[pytesseract: OCR each page]
    G --> D
    E -->|No| H[400 Error: cannot extract text]
    D --> I[RecursiveCharacterTextSplitter\nchunk_size=900, overlap=150]
    I --> J[List of text chunks]
    J --> K[EmbeddingAgent]
    K --> L{Load sentence-transformers\nall-MiniLM-L6-v2}
    L -->|Success| M[384-dim dense vectors]
    L -->|Model unavailable| N[LocalFallbackEmbedder\nhash-based vectors]
    M --> O[ChromaDB: store with metadata\nuser_id, document_id, chunk_index]
    N --> O
    O --> P[Document record saved to SQLite]
```

### Query / Answer Flow

```mermaid
flowchart TD
    A[User asks question] --> B[MultiAgentOrchestrator]
    B --> C{Research query?\nkeywords: arxiv, paper, research}
    C -->|Yes| D[ArxivAgent\nsearch_papers_async]
    C -->|No| E[RAGAgent.collect_contexts]
    D --> F[DDGAgent.search_async]
    E --> G[RetrievalAgent\nChromaDB cosine similarity]
    G --> H{Results found?}
    H -->|No| I[Fallback: query SQLite\ndocument.content_text]
    H -->|Yes| J[Ranked contexts + similarity scores]
    I --> J
    J --> K{max_similarity < 0.5\nor zero contexts?}
    K -->|Yes| L[DDGAgent.search_async\nTavily API]
    K -->|No| M[AnswerGenerationAgent]
    L --> M
    M --> N{LLM_PROVIDER}
    N -->|groq| O[Groq API\nllama-3.1-8b-instant]
    N -->|ollama| P[Ollama local\nllama3]
    O --> Q[Answer text]
    P --> Q
    Q --> R[Save ChatHistory to SQLite]
    R --> S[Return: answer + sources grouped by type]
```

### Embedding Model Details

| Property | Value |
|---|---|
| Model | `sentence-transformers/all-MiniLM-L6-v2` |
| Dimensions | 384 |
| Max sequence length | 256 tokens |
| Similarity metric | Cosine (via ChromaDB L2 → `1 - distance`) |
| Device | Auto (GPU if available, CPU fallback) |
| Fallback | `LocalFallbackEmbedder` (hash-based, same dimensionality) |

### Agent Configuration

| Agent | Purpose | External API | Caching | Rate Limit |
|---|---|---|---|---|
| `DocumentProcessingAgent` | PDF extraction + chunking | None | No | No |
| `EmbeddingAgent` | Encode chunks, index to ChromaDB | None | No | No |
| `RetrievalAgent` | Vector similarity search | ChromaDB (local) | No | No |
| `RAGAgent` | Context collection + confidence scoring | ChromaDB | No | No |
| `AnswerGenerationAgent` | LLM answer synthesis | Groq / Ollama | No | No |
| `ArxivAgent` | Academic paper search | Arxiv API | 15-min TTL | 3.5 s/request |
| `DDGAgent` | Web search | Tavily API | No | 1 s/request |
| `MultiAgentOrchestrator` | Route, combine, normalize | All above | No | No |

---

## Authentication Flow

### Email / Password

```mermaid
sequenceDiagram
    actor User
    participant FE as Frontend
    participant BE as FastAPI Backend
    participant DB as SQLite

    User->>FE: Fills register/login form
    FE->>BE: POST /auth/register { name, email, password }
    BE->>BE: Normalize email (lowercase)
    BE->>DB: Check email uniqueness
    BE->>BE: Hash password\n(PBKDF2-SHA256, 100k iterations)
    BE->>DB: INSERT users row
    BE->>BE: Create JWT\n(HMAC-SHA256, 7-day exp)
    BE-->>FE: { token, user }
    FE->>FE: Store token in localStorage\n+ set access_token cookie
    FE-->>User: Redirect to dashboard
```

### Google OAuth

```mermaid
sequenceDiagram
    actor User
    participant FE as Frontend
    participant FB as Firebase Auth
    participant BE as FastAPI Backend
    participant FBA as Firebase Admin SDK
    participant DB as SQLite

    User->>FE: Click "Sign in with Google"
    FE->>FB: signInWithPopup(GoogleAuthProvider)
    FB-->>FE: Google ID token (idToken)
    FE->>BE: POST /auth/google { idToken }
    BE->>FBA: verify_id_token(idToken)
    FBA-->>BE: { email, name, uid }
    BE->>DB: Upsert user (create if new)
    BE->>BE: Create JWT (same as email/password)
    BE-->>FE: { token, user }
    FE->>FE: Store token + set cookie
    FE-->>User: Redirect to dashboard
```

### JWT Token Anatomy

```
Format: <payload_b64url>.<signature_b64url>

Payload (decoded):
{
  "user_id": 1,
  "email": "jane@example.com",
  "exp": 1751500000
}

Signature: HMAC-SHA256(payload_b64url, AUTH_SECRET)
```

**Verification flow:** Extract token from `Authorization: Bearer` header or `access_token` cookie → split by `.` → recompute and compare signatures (constant-time) → check `exp` timestamp.

---

## Database Schema

```mermaid
erDiagram
    users {
        int id PK
        string name
        string email
        string password_hash
        datetime created_at
    }

    documents {
        int id PK
        int user_id FK
        string filename
        text content_preview
        text content_text
        datetime created_at
    }

    chat_history {
        int id PK
        int user_id FK
        int document_id FK
        text question
        text answer
        text sources_json
        datetime created_at
    }

    users ||--o{ documents : "owns"
    users ||--o{ chat_history : "has"
    documents ||--o{ chat_history : "belongs to"
```

### Table Details

**`users`**
| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | Auto-increment |
| `name` | String(120) | Display name |
| `email` | String(255) | Unique, lowercase-normalized |
| `password_hash` | String(255) | `{salt}${pbkdf2_digest}`, empty for OAuth users |
| `created_at` | DateTime (tz) | Server default: now() |

**`documents`**
| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | Auto-increment |
| `user_id` | Integer FK | References `users.id` |
| `filename` | String(255) | Original PDF filename |
| `content_preview` | Text | First ~500 characters of extracted text |
| `content_text` | Text | Full extracted text (used as RAG fallback) |
| `created_at` | DateTime (tz) | Server default: now() |

**`chat_history`**
| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | Auto-increment |
| `user_id` | Integer FK | References `users.id` |
| `document_id` | Integer FK | References `documents.id`, nullable (general queries) |
| `question` | Text | User's original question |
| `answer` | Text | LLM-generated answer |
| `sources_json` | Text | JSON array of `SourceItem` objects |
| `created_at` | DateTime (tz) | Server default: now() |

### ChromaDB (Vector Store)

| Property | Value |
|---|---|
| Collections | One per (user_id, document_id) pair |
| Document ID format | `{document_id}_{chunk_index}` |
| Embedding dimensions | 384 |
| Metadata fields | `user_id`, `document_id`, `source` (filename), `chunk_index` |
| Similarity filter | By `user_id` + optional `document_id` |

---

## Screenshots

> Add screenshots here after running the application locally.

| Page | Screenshot |
|---|---|
| Landing Page | `docs/screenshots/landing.png` |
| Login / Register | `docs/screenshots/login.png` |
| Dashboard | `docs/screenshots/dashboard.png` |
| Document Upload | `docs/screenshots/upload.png` |
| Chat Interface | `docs/screenshots/chat.png` |
| Chat with Sources | `docs/screenshots/chat-sources.png` |

---

## Deployment

> The current codebase is configured for local development only. No Docker or cloud deployment files are included. Below are recommended steps for a production deployment.

### Recommended Production Stack

```mermaid
graph LR
    subgraph Cloud
        FE[Frontend\nVercel / Netlify]
        BE[Backend\nRender / Railway / EC2]
        DB[(PostgreSQL\nNeon / Supabase / RDS)]
        VEC[(ChromaDB Server\nor Qdrant Cloud)]
    end

    FE -->|HTTPS API calls| BE
    BE --> DB
    BE --> VEC
```

### Steps

1. **Database** — Switch `DATABASE_URL` to a PostgreSQL connection string. The SQLAlchemy ORM and auto-migration code in `database.py` are already compatible.

2. **Vector Store** — Point `CHROMA_PERSIST_DIRECTORY` to a persistent volume, or migrate to a hosted solution (Qdrant, Pinecone).

3. **Backend** — Build a `Dockerfile` and deploy to Render, Railway, or any container platform:
   ```dockerfile
   FROM python:3.11-slim
   WORKDIR /app
   COPY requirements.txt .
   RUN pip install -r requirements.txt
   COPY . .
   CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
   ```

4. **Frontend** — Run `npm run build` in `frontend/` and deploy the output to Vercel (zero-config Next.js support). Set all `NEXT_PUBLIC_*` environment variables in the Vercel dashboard.

5. **Secrets** — Set production environment variables via the platform's secret manager. Critical changes:
   - `AUTH_SECRET` → strong random string (≥32 chars)
   - `ENVIRONMENT=production` (enables secure cookies)
   - `ALLOWED_ORIGINS` → your frontend domain

6. **OCR** — Install Tesseract in the container or Dockerfile if OCR is required in production.

---

## Future Improvements

| Improvement | Rationale |
|---|---|
| Docker + docker-compose | One-command local setup, production parity |
| Refresh token mechanism | Current JWTs have no refresh — users get logged out after 7 days |
| Pagination for chat history | Large conversation histories will cause performance issues |
| Streaming LLM responses | Real-time token streaming via Server-Sent Events for better UX |
| Multi-document queries | Currently queries one document at a time |
| Configurable chunking strategy | Adaptive chunk sizes based on document type (academic, legal, narrative) |
| Domain-specific fine-tuned embeddings | Better retrieval accuracy for specialized domains |
| PostgreSQL in development | Eliminate SQLite/PostgreSQL divergence issues before reaching production |
| CI/CD pipeline | GitHub Actions for lint, test, and deploy on push |
| Metrics + observability | Prometheus/Grafana integration for retrieval quality and LLM latency |
| Rate limiting | Per-user API rate limits to prevent abuse |
| File type expansion | Support DOCX, HTML, and plain text alongside PDF |
| Test suite | Unit tests for agents, integration tests for API endpoints |

---

## Troubleshooting

### Backend fails to start

**Symptom:** `ModuleNotFoundError` on `uvicorn backend.main:app`

**Fix:** Run from the repo root with the virtual environment activated:
```powershell
venv\Scripts\activate
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8001
```

---

### ChromaDB persistence error

**Symptom:** `chromadb.errors.InvalidCollectionException` or path errors

**Fix:** Ensure `CHROMA_PERSIST_DIRECTORY` points to an existing, writable directory, or remove it to use the default:
```powershell
$env:CHROMA_PERSIST_DIRECTORY = "C:\Users\YourName\.ai-assistant\chroma"
```

---

### OCR not working

**Symptom:** `TesseractNotFoundError` or scanned PDFs return empty text

**Fix:**
1. Install Tesseract: [UB Mannheim installer](https://github.com/UB-Mannheim/tesseract/wiki) (Windows)
2. Set `TESSERACT_CMD` in `.env` to the full path:
   ```
   TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
   ```
3. Ensure `OCR_FALLBACK_ENABLED=true`

---

### Groq API errors

**Symptom:** `401 Unauthorized` or `429 Rate Limited` from Groq

**Fix:** Verify `GROQ_API_KEY` is set and valid. For rate limits, switch to `LLM_PROVIDER=ollama` locally.

---

### Google sign-in fails

**Symptom:** `Firebase ID token verification failed`

**Fix:** Ensure all three Firebase backend variables are set correctly:
```
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_CLIENT_EMAIL=firebase-adminsdk-xxx@your-project-id.iam.gserviceaccount.com
FIREBASE_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----\n"
```
Note: In `.env`, the private key newlines must be literal `\n` escape sequences (not actual newlines).

---

### Frontend cannot reach backend

**Symptom:** Network errors or CORS failures in browser

**Fix:** Check that:
1. `NEXT_PUBLIC_API_BASE_URL` in `frontend/.env.local` matches the port you started the backend on
2. `ALLOWED_ORIGINS` in `.env` includes `http://localhost:3000`
3. Both frontend and backend are running simultaneously

---

### Embedding model download is slow or fails

**Symptom:** First startup hangs or `OSError` when loading the embedding model

**Fix:** The model (`all-MiniLM-L6-v2`) is ~90 MB and downloads from HuggingFace on first run. Ensure internet access. If the model cannot be loaded, the system automatically falls back to a hash-based embedder — retrieval quality will be degraded but the application will still function.

---

## Contributing

Contributions are welcome. Please follow these guidelines:

1. **Fork** the repository and create a feature branch from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Code style:**
   - Python: Follow PEP 8. Use type hints throughout.
   - TypeScript: Strict mode is enabled. No `any` types.
   - Keep agent classes single-responsibility.

3. **Testing:** Add or update tests for any changed logic. At minimum, test the happy path and one failure mode.

4. **Commits:** Write descriptive commit messages:
   ```
   feat(rag): add re-ranking step after vector retrieval
   fix(auth): handle expired Firebase tokens gracefully
   ```

5. **Pull Request:** Open a PR against `main` with:
   - A clear description of what changed and why
   - Steps to test the change locally
   - Screenshots for UI changes

6. **Security:** Never commit API keys, secrets, or service account files. Double-check `.gitignore` before pushing.

---

## License

This project is licensed under the **MIT License**.

```
MIT License

Copyright (c) 2025 Satyam Mishra

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

---

# README Audit Report

## Features Confirmed in Code

| Feature | Location | Status |
|---|---|---|
| PDF upload + text extraction | `backend/agents/document_processing_agent.py` | Implemented |
| OCR fallback (PyMuPDF + Tesseract) | `backend/services/pdf_service.py` + `document_processing_agent.py` | Implemented |
| Text chunking (RecursiveCharacterTextSplitter) | `document_processing_agent.py` | Implemented |
| Sentence-transformer embeddings (384-dim) | `backend/services/embedding_backend.py` | Implemented |
| Hash-based embedding fallback | `embedding_backend.py` (`LocalFallbackEmbedder`) | Implemented |
| ChromaDB vector indexing and search | `backend/agents/embedding_agent.py`, `retrieval_agent.py` | Implemented |
| ChromaDB RAG fallback to SQLite | `backend/agents/rag_agent.py` | Implemented |
| Multi-agent orchestration | `backend/agents/orchestrator.py` | Implemented |
| Arxiv paper search (async, cached, rate-limited) | `backend/agents/arxiv_agent.py` | Implemented |
| Tavily web search (async, rate-limited) | `backend/agents/ddg_agent.py` | Implemented |
| Groq LLM integration | `backend/agents/answer_generation_agent.py` | Implemented |
| Ollama LLM integration | `answer_generation_agent.py` | Implemented |
| Email/password registration and login | `backend/routes/auth.py`, `services/auth_service.py` | Implemented |
| Google OAuth via Firebase | `auth_service.py`, `frontend/components/auth-provider.tsx` | Implemented |
| Custom JWT (HMAC-SHA256) | `auth_service.py` | Implemented |
| HttpOnly cookie session | `auth.py` (set-cookie on login) | Implemented |
| SQLAlchemy ORM + auto-migration | `backend/database.py` | Implemented |
| Chat history persistence | `backend/models.py` (`ChatHistory`), `orchestrator.py` | Implemented |
| Document deletion (SQL + ChromaDB) | `backend/routes/rag.py` | Implemented |
| Protected Next.js routes | `frontend/components/auth-guard.tsx` | Implemented |
| Dark/light theme toggle | `frontend/components/theme-toggle.tsx` | Implemented |
| Markdown rendering for answers | `frontend/components/markdown-message.tsx` | Implemented |
| Toast notifications | `frontend/components/toast-provider.tsx` | Implemented |
| Typed frontend API client | `frontend/lib/api.ts` | Implemented |

---

## Missing Documentation (in old README)

| Gap | Impact |
|---|---|
| No Mermaid architecture or flow diagrams | Readers cannot understand system without reading source |
| No detailed API request/response docs | Frontend/external developers cannot integrate |
| No database ER diagram | Schema relationships unclear |
| No authentication flow diagram | Security model opaque |
| No ML pipeline explanation | AI/RAG internals undocumented |
| No per-variable explanation in env docs | Developers must read `config.py` to understand each variable |
| No troubleshooting section | Common setup failures undocumented |
| No deployment guidance | No path from local to production |
| No contributing guidelines | External contributors have no standards to follow |
| No license | Repository technically has no usage rights declared |

---

## Dead Code / Unused Files

| File | Issue |
|---|---|
| `backend/services/chroma_service.py` | Empty placeholder — functionality lives in `vector_store.py` and agents |
| `backend/services/chunk_service.py` | Empty placeholder — chunking lives in `document_processing_agent.py` |
| `backend/services/embedding_service.py` | Empty placeholder — embedding lives in `embedding_agent.py` and `embedding_backend.py` |
| `backend/auth/` directory | Mentioned in codebase but auth logic is in `backend/services/auth_service.py` and `backend/routes/auth.py` |
| `NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET` | Declared in `.env.example` but never used in code |
| `NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID` | Declared in `.env.example` but never used in code |
| `frontend/lib/document-display.ts` | Utility file with unclear usage |

---

## Incomplete Features

| Feature | Status | Notes |
|---|---|---|
| Pagination for chat history | Partial | `limit` param exists but no `offset` — no true pagination |
| Refresh tokens | Missing | JWT expires in 7 days with no refresh mechanism |
| Multi-document querying | Missing | Each query is scoped to one `document_id` |
| Unit / integration tests | Missing | No test files found anywhere in the repo |
| CI/CD pipeline | Missing | No `.github/workflows/` or equivalent |
| Production deployment config | Missing | No Dockerfile, docker-compose, or cloud config |
| Alembic migrations | Installed | `alembic` is in `requirements.txt` but migrations are ad-hoc in `database.py` via `ALTER TABLE` |

---

## Security Concerns

| Concern | Severity | Location | Recommendation |
|---|---|---|---|
| Default `AUTH_SECRET` in code | **High** | `config.py` | Enforce non-default secret in production via startup check |
| Firebase token verification failure can silently fall through | **Medium** | `auth_service.py` | Raise `401` immediately on any verification exception; do not use unverified token data |
| No API rate limiting | **Medium** | All routes | Add per-user rate limiting (e.g., `slowapi`) to prevent abuse |
| `user_id` accepted in request body | **Low** | `rag.py`, `chat.py` | Always derive `user_id` from the JWT token, not request body, to prevent privilege escalation |
| SQLite not safe for multi-user production | **Medium** | `database.py` | Use PostgreSQL with proper connection pooling in production |
| No Content Security Policy headers | **Low** | `main.py` | Add security headers middleware (e.g., `starlette-csrf`) |
| `app.db` not in `.gitignore` top-level entry | **Low** | `.gitignore` | Confirm `app.db` is excluded — it may contain user data |

---

## Improvements for GitHub Presentation

| Improvement | Description |
|---|---|
| Add a project banner / logo | A hero image or ASCII banner at the top of the README significantly improves first impressions |
| Add badges | Build status, Python version, Node version, license badge, last-commit badge |
| Add a live demo link | If deployed, link to the live instance at the top |
| Add a GIF demo | A 30-second GIF showing upload → ask → answer is more compelling than any text description |
| Create `docs/screenshots/` directory | Populate with actual screenshots for the table provided in this README |
| Add `CONTRIBUTING.md` | Elevate the contribution guide to its own file for discoverability |
| Add `SECURITY.md` | Document responsible disclosure policy |
| Add GitHub issue templates | Bug report and feature request templates (`.github/ISSUE_TEMPLATE/`) |
| Add GitHub PR template | Standardize pull request descriptions |
| Clean up placeholder service files | Remove or implement `chroma_service.py`, `chunk_service.py`, `embedding_service.py` to reduce confusion |
| Add a `Makefile` | `make dev`, `make install`, `make test` — reduces onboarding friction |
