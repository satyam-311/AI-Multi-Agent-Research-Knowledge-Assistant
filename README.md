# AI Multi-Agent Research Knowledge Assistant

Full-stack research assistant for uploading documents, retrieving grounded context, and generating answers through a multi-agent RAG pipeline. The project combines a Next.js frontend, a FastAPI backend, SQLite/SQLAlchemy for app data, ChromaDB for vector retrieval, and Firebase-backed authentication.

## What It Does

- Upload PDF documents and chunk them for retrieval.
- Ask questions against a specific document and get grounded answers with source references.
- Store chat history per user and document.
- Support email/password auth and Google sign-in.
- Extend retrieval with dedicated research agents such as Arxiv, DuckDuckGo, and RAG orchestration components.

## Stack

- Frontend: Next.js 16, React 19, TypeScript, Tailwind CSS
- Backend: FastAPI, SQLAlchemy, Pydantic
- Vector store: ChromaDB
- Embeddings: `sentence-transformers/all-MiniLM-L6-v2`
- LLM providers: Groq or Ollama
- Auth: Firebase Admin on the backend, Firebase Web SDK on the frontend
- OCR fallback: PyMuPDF, Pillow, pytesseract

## Current Architecture

### Frontend

- Login flow with Firebase client integration
- Protected workspace/dashboard UI
- Document upload and chat workspace
- API client layer for auth, document, and chat actions

### Backend

- `backend/routes/auth.py`: register, login, Google login, current user, logout
- `backend/routes/chat.py`: ask questions and fetch chat history
- `backend/routes/rag.py`: upload documents, list documents, ask questions, fetch history, delete documents
- `backend/services/rag_service.py`: main document ingestion and retrieval workflow
- `backend/agents/`: retrieval, answer generation, orchestrator, Arxiv, DuckDuckGo, and RAG-specific agents

### Data Flow

1. User authenticates from the frontend.
2. A PDF is uploaded to the FastAPI backend.
3. The backend extracts text, chunks it, embeds the chunks, and stores vectors in ChromaDB.
4. The user asks a question tied to a document.
5. Retrieval agents collect relevant context.
6. The answer generation layer calls the configured LLM provider.
7. The API returns the answer plus normalized source metadata.

## Project Structure

```text
AI-Multi-Agent-Research-Knowledge-Assistant/
|-- backend/
|   |-- agents/
|   |-- routes/
|   |-- services/
|   |-- config.py
|   |-- database.py
|   |-- main.py
|   |-- models.py
|   `-- schemas.py
|-- frontend/
|   |-- app/
|   |-- components/
|   |-- lib/
|   |-- package.json
|   `-- tsconfig.json
|-- .env.example
|-- .gitignore
|-- README.md
`-- requirements.txt
```

## Environment Variables

Copy the example files and fill in real values locally:

```powershell
Copy-Item .env.example .env
Copy-Item frontend\.env.example frontend\.env.local
```

Important backend variables:

- `DATABASE_URL`
- `CHROMA_PERSIST_DIRECTORY`
- `LLM_PROVIDER`
- `GROQ_API_KEY`
- `OLLAMA_BASE_URL`
- `OLLAMA_MODEL`
- `AUTH_SECRET`
- `FIREBASE_PROJECT_ID`
- `FIREBASE_CLIENT_EMAIL`
- `FIREBASE_PRIVATE_KEY`
- `FIREBASE_SERVICE_ACCOUNT_JSON`
- `FIREBASE_SERVICE_ACCOUNT_KEY_PATH`
- `TAVILY_API_KEY`

Important frontend variables:

- `NEXT_PUBLIC_API_BASE_URL`
- `NEXT_PUBLIC_FIREBASE_API_KEY`
- `NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN`
- `NEXT_PUBLIC_FIREBASE_PROJECT_ID`
- `NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET`
- `NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID`
- `NEXT_PUBLIC_FIREBASE_APP_ID`

Do not commit `.env`, `frontend/.env.local`, service account JSON files, local databases, or generated build folders.

## Local Setup

### Backend

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8001
```

The backend loads environment values from the repo root `.env`.

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Default local URLs:

- Frontend: `http://localhost:3000`
- Backend API: `http://127.0.0.1:8001`
- FastAPI docs: `http://127.0.0.1:8001/docs`

## API Overview

### Auth

- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/google`
- `GET /auth/me`
- `POST /auth/logout`

### Chat

- `POST /chat`
- `GET /chat/history`

### RAG

- `POST /rag/upload_document`
- `POST /rag/ask_question`
- `GET /rag/documents`
- `GET /rag/get_chat_history`
- `DELETE /rag/documents/{document_id}`

The same router is also exposed under `/api`, so both `/rag/...` and `/api/rag/...` are available.

## Notes

- OCR fallback for scanned PDFs requires Tesseract installed on the host.
- SQLite is the current default local database target.
- Chroma persistence is stored locally unless you point it elsewhere with `CHROMA_PERSIST_DIRECTORY`.
- If you use Groq, set `GROQ_API_KEY`. If you use Ollama, ensure the local Ollama server is running.

## Git Hygiene

Before pushing:

- Keep `.env` and `frontend/.env.local` local only.
- Keep Firebase service account files out of the repo.
- Do not commit `frontend/.next/`, `frontend/.next-build/`, `frontend/.next-cache/`, local databases, or runtime output.
- Review `git status` before `git add`.
