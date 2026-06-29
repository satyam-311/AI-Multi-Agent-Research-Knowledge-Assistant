# AI Multi-Agent Research Knowledge Assistant (MARKA)

**Generative AI | RAG | Multi-Agent Systems**

---

## Project Overview

MARKA is a production-grade multi-agent RAG platform that answers research questions by dynamically routing across document retrieval, academic paper search, and live web search. It combines LangGraph-orchestrated agent workflows with ChromaDB vector retrieval and Llama 3 generation to deliver source-grounded answers with measurably lower hallucination rates than single-pipeline approaches.

---

## Key Features

- **Adaptive Query Routing** — LangGraph workflow dynamically selects between document, web, research, and hybrid agent paths based on query intent classification
- **Multi-Agent Architecture** — Specialized agents for document processing, vector retrieval, ArXiv paper search, web search, and LLM answer synthesis operate as composable, independently testable units
- **Source-Grounded Retrieval** — Every answer is backed by citations from ChromaDB vector search, ArXiv MCP, or web search results, with similarity scores surfaced to the user
- **Hallucination Reduction** — Confidence thresholding on retrieval similarity scores triggers automatic fallback to web search when document context is insufficient
- **User-Specific Knowledge Management** — Per-user, per-document vector namespacing in ChromaDB with full chat history persistence in PostgreSQL
- **OCR-Capable Document Ingestion** — PDF text extraction with automatic PyMuPDF + Tesseract OCR fallback for scanned documents
- **Dual LLM Backend** — Supports Groq API (Llama 3 cloud) and Ollama (local inference) with zero code changes
- **Firebase Authentication** — Email/password and Google OAuth with stateless HMAC-SHA256 JWT sessions
- **Scalable Deployment** — Dockerized services deployable to AWS EC2 with ECR image registry and S3 for document storage

---

## Architecture Flowchart

```mermaid
flowchart TD
    A[User Query] --> B[MultiAgent Orchestrator]
    B --> C{Router Agent\nIntent Classification}

    C -->|Document query| D[Document Agent\nChromaDB retrieval]
    C -->|Research query| E[Research Agent\nArXiv MCP search]
    C -->|Low confidence| F[Web Agent\nTavily web search]
    C -->|Complex query| G[Hybrid Agent\nDocument + Web + ArXiv]

    D --> H[Retrieval Layer\nVector similarity scoring]
    E --> H
    F --> H
    G --> H

    H --> I{Confidence threshold\nmet?}
    I -->|Yes| J[Answer Generation Agent\nLlama 3 via Groq or Ollama]
    I -->|No| F

    J --> K[Source Normalization\nRAG + ArXiv + Web citations]
    K --> L[Response\nAnswer with grounded sources]
    L --> M[PostgreSQL\nChat history persistence]
```

---

## Tech Stack

| Category       | Technology                                          |
|----------------|-----------------------------------------------------|
| LLM            | Llama 3 via Groq API (`llama-3.1-8b-instant`) / Ollama (local) |
| Orchestration  | LangGraph, Multi-Agent Systems                      |
| Retrieval      | RAG pipeline, ArXiv MCP, Tavily Web Search Agent    |
| Vector Store   | ChromaDB with `sentence-transformers/all-MiniLM-L6-v2` (384-dim) |
| Backend        | FastAPI, SQLAlchemy 2.0, Pydantic v2, Uvicorn       |
| Authentication | Firebase Admin SDK (backend) + Firebase Web SDK (frontend) |
| Database       | PostgreSQL (production) / SQLite (local development) |
| DevOps         | Docker, GitHub Actions, AWS EC2 + S3 + ECR          |

---

## Project Structure

```
AI-Multi-Agent-Research-Knowledge-Assistant/
├── backend/
│   ├── agents/
│   │   ├── orchestrator.py              # LangGraph workflow router and agent coordinator
│   │   ├── rag_agent.py                 # RAG context collection with confidence scoring
│   │   ├── retrieval_agent.py           # ChromaDB vector similarity search interface
│   │   ├── answer_generation_agent.py   # Llama 3 answer synthesis via Groq or Ollama
│   │   ├── arxiv_agent.py               # ArXiv paper search with caching and rate limiting
│   │   ├── ddg_agent.py                 # Tavily web search with retry logic
│   │   ├── document_processing_agent.py # PDF extraction, chunking, OCR fallback
│   │   ├── embedding_agent.py           # Chunk embedding and ChromaDB indexing
│   │   └── __init__.py
│   ├── routes/
│   │   ├── auth.py                      # Register, login, Google OAuth, /me, logout
│   │   ├── chat.py                      # Ask question, fetch chat history
│   │   ├── rag.py                       # Upload, list, delete documents
│   │   ├── health.py                    # Liveness health check
│   │   └── __init__.py
│   ├── services/
│   │   ├── auth_service.py              # JWT creation, verification, Firebase token validation
│   │   ├── embedding_backend.py         # Embedding model loader with hash-based fallback
│   │   ├── vector_store.py              # ChromaDB client interface
│   │   ├── pdf_service.py               # OCR service using PyMuPDF and Tesseract
│   │   ├── rag_service.py               # RAG service wrapper
│   │   └── __init__.py
│   ├── config.py                        # Pydantic settings management and .env parsing
│   ├── database.py                      # SQLAlchemy engine, session, auto-migrations
│   ├── models.py                        # ORM models: User, Document, ChatHistory
│   ├── schemas.py                       # Pydantic request and response schemas
│   └── main.py                          # FastAPI app initialization, CORS, router mounting
├── frontend/
│   ├── app/
│   │   ├── (workspace)/                 # Auth-protected route group
│   │   │   ├── chat/page.tsx
│   │   │   ├── dashboard/page.tsx
│   │   │   ├── documents/page.tsx
│   │   │   └── upload/page.tsx
│   │   ├── login/page.tsx
│   │   └── layout.tsx
│   ├── components/
│   │   ├── auth-guard.tsx
│   │   ├── auth-provider.tsx
│   │   ├── chat-workspace.tsx
│   │   ├── app-sidebar.tsx
│   │   └── ui/
│   ├── lib/
│   │   ├── api.ts                       # Typed HTTP client for all backend endpoints
│   │   └── firebase.js
│   ├── package.json
│   └── tsconfig.json
├── requirements.txt
├── Dockerfile
├── .env.example
└── README.md
```

---

## Installation and Setup

### Prerequisites

- Python 3.11+
- Node.js 18+ and npm 9+
- Docker (for containerized deployment)
- Tesseract OCR 5.x (optional, required only for scanned PDFs)

### 1. Clone the Repository

```bash
git clone https://github.com/satyam3112003/AI-Multi-Agent-Research-Knowledge-Assistant.git
cd AI-Multi-Agent-Research-Knowledge-Assistant
```

### 2. Create and Activate a Virtual Environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Frontend Dependencies

```bash
cd frontend
npm install
cd ..
```

### 5. Configure Environment Variables

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env.local
```

Edit `.env` with your credentials:

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/marka

# Vector Store
CHROMA_PERSIST_DIRECTORY=~/.marka/chroma

# LLM Provider
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_your_groq_api_key
GROQ_MODEL=llama-3.1-8b-instant

# Authentication
AUTH_SECRET=your-strong-random-secret-min-32-chars
ENVIRONMENT=production

# Firebase
FIREBASE_PROJECT_ID=your-firebase-project-id
FIREBASE_CLIENT_EMAIL=firebase-adminsdk@your-project.iam.gserviceaccount.com
FIREBASE_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----\n"

# Web Search
TAVILY_API_KEY=tvly_your_tavily_api_key

# CORS
ALLOWED_ORIGINS=http://localhost:3000
```

### 6. Start the Backend

```bash
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8001
```

Interactive API documentation is available at `http://127.0.0.1:8001/docs`.

### 7. Start the Frontend

```bash
cd frontend
npm run dev
```

The application is available at `http://localhost:3000`.

---

## API Endpoints

| Method   | Endpoint                        | Description                                              | Auth Required |
|----------|---------------------------------|----------------------------------------------------------|---------------|
| `POST`   | `/auth/register`                | Register a new user with email and password              | No            |
| `POST`   | `/auth/login`                   | Authenticate an existing user, returns JWT               | No            |
| `POST`   | `/auth/google`                  | Exchange a Firebase Google ID token for a backend JWT    | No            |
| `GET`    | `/auth/me`                      | Return the currently authenticated user profile          | Yes           |
| `POST`   | `/auth/logout`                  | Invalidate the session cookie                            | Yes           |
| `POST`   | `/rag/upload_document`          | Upload a PDF, extract, chunk, embed, and index to ChromaDB | Yes         |
| `GET`    | `/rag/documents`                | List all documents belonging to the authenticated user   | Yes           |
| `DELETE` | `/rag/documents/{document_id}`  | Delete a document and its vector embeddings              | Yes           |
| `POST`   | `/chat`                         | Submit a query and receive a source-grounded answer      | Yes           |
| `GET`    | `/chat/history`                 | Retrieve paginated chat history for a document           | Yes           |
| `GET`    | `/health`                       | Liveness health check for load balancer probes           | No            |

---

## How It Works

1. **Authentication** — The user authenticates via email/password or Google OAuth through Firebase. The backend issues a stateless HMAC-SHA256 JWT stored as an HttpOnly cookie, identifying all subsequent requests to user-scoped data.

2. **Document Ingestion** — The user uploads a PDF. The Document Processing Agent extracts text using `pypdf`, falling back to PyMuPDF + Tesseract OCR for scanned pages. The extracted text is split into 900-character chunks with 150-character overlap by a `RecursiveCharacterTextSplitter`.

3. **Embedding and Indexing** — The Embedding Agent encodes each chunk using `sentence-transformers/all-MiniLM-L6-v2` to produce 384-dimensional dense vectors. These are stored in ChromaDB under a collection namespaced by `(user_id, document_id)` for strict data isolation.

4. **Query Routing** — When the user submits a query, the MultiAgent Orchestrator classifies intent. Queries containing research-oriented keywords trigger the ArXiv Research Agent. All queries first attempt vector retrieval against the user's document collection.

5. **Retrieval** — The Retrieval Agent performs cosine similarity search in ChromaDB, returning the top-k chunks with similarity scores. If maximum similarity falls below the 0.5 confidence threshold, the Web Agent fires a Tavily API request to supplement context with live web results.

6. **Answer Generation** — The Answer Generation Agent assembles a structured prompt from retrieved document chunks, ArXiv paper summaries, and web snippets, then calls the Llama 3 model via Groq API (or Ollama for local inference) to synthesize a coherent, cited response.

7. **Source Normalization** — The orchestrator groups sources by type (`rag`, `arxiv`, `web`) and attaches them to the response alongside similarity scores, paper URLs, and web snippet metadata so users can verify every claim.

8. **Persistence** — The question, generated answer, and full source payload are saved to PostgreSQL `chat_history`, enabling per-user conversation replay across sessions.

---

## Future Improvements

- **Streaming LLM Responses** — Implement Server-Sent Events for real-time token streaming to eliminate perceived latency on long-form answers
- **Cross-Document Query Mode** — Extend the routing logic to retrieve across all of a user's documents simultaneously rather than scoping each query to a single document
- **Re-ranking Layer** — Add a cross-encoder re-ranking step after initial vector retrieval to improve precision before passing context to the generation agent
- **Adaptive Chunking Strategy** — Use document type classification (academic, legal, narrative) to select chunk sizes and overlap ratios dynamically rather than applying fixed parameters
- **Observability Pipeline** — Integrate Prometheus metrics and Grafana dashboards to track retrieval confidence distributions, LLM latency, and per-agent error rates in production

---

## License

MIT License

Copyright (c) 2025 Satyam Mishra

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
