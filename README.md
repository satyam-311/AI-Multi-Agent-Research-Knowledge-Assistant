# AI Multi-Agent Research Knowledge Assistant

Initial full-stack project scaffold for a multi-agent RAG application where users upload PDFs and ask grounded questions.

## 1. Project Architecture

### High-level flow
1. User uploads a PDF from the Next.js dashboard.
2. FastAPI receives the file.
3. `DocumentProcessingAgent` extracts PDF text and chunks it.
4. `EmbeddingAgent` embeds chunks using Sentence Transformers and stores vectors in ChromaDB.
5. User asks a question in chat.
6. `RetrievalAgent` fetches relevant chunks from ChromaDB.
7. `AnswerGenerationAgent` calls `llama3` via Ollama with retrieved context.
8. API returns answer + source metadata to frontend.

### System components
- Frontend: Next.js + Tailwind CSS + shadcn/ui-style components + lucide icons.
- Backend API: FastAPI.
- Relational DB: PostgreSQL (document metadata).
- Vector DB: ChromaDB (semantic chunk search).
- LLM runtime: Ollama (`llama3`).
- Embeddings: `sentence-transformers/all-MiniLM-L6-v2`.

### Agent responsibilities
- `DocumentProcessingAgent`: PDF extraction + text chunking.
- `EmbeddingAgent`: embedding generation + Chroma indexing.
- `RetrievalAgent`: semantic retrieval for user question.
- `AnswerGenerationAgent`: grounded answer generation via Ollama llama3.

## 2. Folder Structure

```text
AI-Multi-Agent-Research-Knowledge-Assistant/
├── .env.example
├── requirements.txt
├── README.md
├── backend/
│   ├── .env.example
│   ├── __init__.py
│   ├── config.py
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── health.py
│   │   ├── documents.py
│   │   └── chat.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── pdf_service.py
│   │   ├── chunk_service.py
│   │   ├── embedding_service.py
│   │   ├── chroma_service.py
│   │   └── rag_service.py
│   └── agents/
│       ├── __init__.py
│       ├── document_processing_agent.py
│       ├── embedding_agent.py
│       ├── retrieval_agent.py
│       ├── answer_generation_agent.py
│       └── orchestrator.py
└── frontend/
    ├── package.json
    ├── tsconfig.json
    ├── next-env.d.ts
    ├── next.config.mjs
    ├── postcss.config.mjs
    ├── tailwind.config.ts
    ├── app/
    │   ├── layout.tsx
    │   ├── page.tsx
    │   └── globals.css
    ├── components/
    │   ├── dashboard-shell.tsx
    │   ├── sidebar.tsx
    │   ├── upload-panel.tsx
    │   ├── chat-panel.tsx
    │   └── ui/
    │       ├── badge.tsx
    │       ├── button.tsx
    │       ├── card.tsx
    │       └── input.tsx
    ├── lib/
    │   └── utils.ts
    ├── ui/
    │   └── index.ts
    └── pages/
        └── README.md
```

## 3. Setup (Scaffold Stage)

### Backend
```bash
python -m venv venv
venv\\Scripts\\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

OCR fallback for scanned PDFs requires the Tesseract OCR engine installed on the host. If the `tesseract` binary is not on PATH, set `TESSERACT_CMD` in `.env` to the full path (for example `C:\\Program Files\\Tesseract-OCR\\tesseract.exe`).

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## 4. API Skeleton Endpoints

- `GET /api/health`
- `POST /api/documents/upload`
- `POST /api/chat/ask`

## 5. Current Status

- Completed:
  - Architecture and file structure
  - Backend skeleton with multi-agent modules
  - Frontend skeleton with modern dashboard UI direction
  - Base environment and dependency manifests
- Deferred (next phase):
  - Full agent orchestration and error handling
  - Async processing jobs
  - Auth, document management, chat history
  - Production hardening and tests
