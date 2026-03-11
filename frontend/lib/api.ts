const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000").replace(
  /\/$/,
  ""
);
const REQUEST_TIMEOUT_MS = 120_000;

export type HealthResponse = {
  status: string;
  message: string;
};

export type AuthUser = {
  id: number;
  name: string;
  email: string;
  created_at: string;
};

export type AuthResponse = {
  token: string;
  user: AuthUser;
};

export type DocumentUploadResponse = {
  document_id: number;
  user_id: number;
  filename: string;
  chunks_created: number;
};

export type AskResponse = {
  user_id: number;
  answer: string;
  sources: string[];
};

export type DocumentRecord = {
  id: number;
  user_id: number;
  filename: string;
  content_preview: string;
  created_at: string;
};

export type ChatHistoryRecord = {
  id: number;
  user_id: number;
  document_id: number | null;
  question: string;
  answer: string;
  sources: string[];
  created_at: string;
};

export type DeleteDocumentResponse = {
  document_id: number;
  deleted: boolean;
};

const AUTH_STORAGE_KEY = "auth_session";

type StoredAuthSession = {
  token: string;
  user: AuthUser;
};

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function getStoredAuthSession(): StoredAuthSession | null {
  if (typeof window === "undefined") {
    return null;
  }

  const raw = window.localStorage.getItem(AUTH_STORAGE_KEY);
  if (!raw) {
    return null;
  }

  try {
    return JSON.parse(raw) as StoredAuthSession;
  } catch {
    window.localStorage.removeItem(AUTH_STORAGE_KEY);
    return null;
  }
}

function getAuthHeaders(): HeadersInit | undefined {
  const session = getStoredAuthSession();
  if (!session) {
    return undefined;
  }
  return {
    Authorization: `Bearer ${session.token}`
  };
}

export function setAuthSession(session: StoredAuthSession): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(session));
}

export function clearAuthSession(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(AUTH_STORAGE_KEY);
}

export function getAuthSession(): StoredAuthSession | null {
  return getStoredAuthSession();
}

async function parseJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = "Request failed.";
    try {
      const body = (await response.json()) as { detail?: string };
      detail = body.detail ?? detail;
    } catch {
      detail = response.statusText || detail;
    }
    throw new ApiError(detail, response.status);
  }

  return (await response.json()) as T;
}

type UploadOptions = {
  onProgress?: (progress: number) => void;
};

type RequestOptions = {
  method?: "GET" | "POST" | "DELETE";
  body?: BodyInit | null;
  headers?: HeadersInit;
  timeoutMs?: number;
};

async function requestJson<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(
    () => controller.abort(new Error("Request timed out.")),
    options.timeoutMs ?? REQUEST_TIMEOUT_MS
  );

  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method: options.method ?? "GET",
      headers: {
        ...getAuthHeaders(),
        ...options.headers
      },
      body: options.body,
      credentials: "include",
      cache: "no-store",
      signal: controller.signal
    });

    return await parseJson<T>(response);
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }

    if (error instanceof Error && error.name === "AbortError") {
      throw new Error("This response is taking longer than expected. Please wait a bit and try again.");
    }

    throw new Error(
      error instanceof Error ? error.message : "Network error. Please try again."
    );
  } finally {
    clearTimeout(timeout);
  }
}

export async function getHealth(): Promise<HealthResponse> {
  return requestJson<HealthResponse>("/health");
}

export async function listDocuments(): Promise<DocumentRecord[]> {
  return requestJson<DocumentRecord[]>("/rag/documents");
}

export async function listChatHistory(): Promise<ChatHistoryRecord[]> {
  return requestJson<ChatHistoryRecord[]>("/rag/get_chat_history");
}

export async function uploadDocument(
  file: File,
  options?: UploadOptions
): Promise<DocumentUploadResponse> {
  if (!file.name.toLowerCase().endsWith(".pdf")) {
    throw new Error("Only PDF files are supported.");
  }

  return new Promise<DocumentUploadResponse>((resolve, reject) => {
    const formData = new FormData();
    formData.append("file", file);

    const request = new XMLHttpRequest();
    request.open("POST", `${API_BASE_URL}/rag/upload_document`);
    request.responseType = "json";
    request.timeout = REQUEST_TIMEOUT_MS;
    request.withCredentials = true;
    const session = getStoredAuthSession();
    if (session?.token) {
      request.setRequestHeader("Authorization", `Bearer ${session.token}`);
    }

    request.upload.onprogress = (event) => {
      if (!event.lengthComputable || !options?.onProgress) {
        return;
      }

      options.onProgress(Math.round((event.loaded / event.total) * 100));
    };

    request.onload = () => {
      if (request.status >= 200 && request.status < 300) {
        resolve(request.response as DocumentUploadResponse);
        return;
      }

      const detail =
        (request.response as { detail?: string } | null)?.detail ?? "Upload failed.";
      reject(new ApiError(detail, request.status));
    };

    request.onerror = () =>
      reject(new Error("Network error during upload. Please try again."));
    request.ontimeout = () =>
      reject(new Error("Upload is taking longer than expected. Please wait a bit and try again."));
    request.send(formData);
  });
}

export async function askQuestion(params: {
  question: string;
  documentId?: number | null;
  topK?: number;
}): Promise<AskResponse> {
  return requestJson<AskResponse>("/rag/ask_question", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      question: params.question,
      top_k: params.topK ?? 4,
      document_id: params.documentId ?? null
    })
  });
}

export async function deleteDocument(documentId: number): Promise<DeleteDocumentResponse> {
  return requestJson<DeleteDocumentResponse>(`/rag/documents/${documentId}`, {
    method: "DELETE"
  });
}

export async function register(params: {
  name: string;
  email: string;
  password: string;
}): Promise<AuthResponse> {
  return requestJson<AuthResponse>("/auth/register", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(params)
  });
}

export async function login(params: { email: string; password: string }): Promise<AuthResponse> {
  return requestJson<AuthResponse>("/auth/login", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(params)
  });
}

export async function getCurrentUser(): Promise<AuthUser> {
  return requestJson<AuthUser>("/auth/me");
}

export async function logout(): Promise<void> {
  await requestJson<{ logged_out: boolean }>("/auth/logout", {
    method: "POST"
  });
  clearAuthSession();
}
