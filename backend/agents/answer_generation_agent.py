# answer_generation_agent.py
# LLM answer synthesis agent for the MARKA pipeline.
# Builds a structured prompt from retrieved contexts and calls either the
# Groq API (Llama 3 cloud) or a local Ollama instance to generate a
# source-grounded response. The provider is selected at runtime via config.

# Third-party HTTP client for synchronous Groq API requests
import httpx
# Official Ollama Python client for local LLM inference
import ollama

# Runtime configuration (LLM provider, model names, API keys, base URLs)
from backend.config import get_settings


class AnswerGenerationAgent:
    """
    LLM-based answer synthesis agent that generates responses from retrieved contexts.

    Supports two interchangeable LLM backends selected via the LLM_PROVIDER
    environment variable:
    - "groq": Calls the Groq cloud API (Llama 3.1-8b-instant) via HTTP.
    - "ollama": Calls a local Ollama server running the llama3 model.

    The agent is intentionally context-only: it instructs the LLM to answer
    strictly from the provided sources and to explicitly state when evidence is
    missing rather than speculating, which reduces hallucination risk.

    Attributes:
        settings: Parsed application settings including provider selection and API keys.
        model (str): The Ollama model name (used only when provider is "ollama").
        client (ollama.Client): Pre-initialized Ollama client (used when provider is "ollama").
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.settings = settings
        # The Ollama client and model are always initialized so we can switch providers
        # at runtime without restarting the server
        self.model = settings.ollama_model
        self.client = ollama.Client(host=settings.ollama_base_url)

    def generate_answer(self, question: str, contexts: list[dict]) -> str:
        """
        Generate a source-grounded answer from retrieved contexts.

        Builds a structured prompt that includes intent-specific guidance,
        the user's question, and all retrieved context chunks, then dispatches
        to the configured LLM backend.

        Args:
            question (str): The original user question as submitted to the API.
            contexts (list[dict]): Normalized context dicts from the RAG, ArXiv,
                or web search agents, each containing at minimum a "text" key
                and source metadata fields.

        Returns:
            str: The LLM-generated answer string, or a descriptive error message
            if the backend is unavailable.
        """
        if not contexts:
            return "I could not find relevant context in uploaded documents."

        guidance = self._build_guidance(question)
        context_text = "\n\n".join([self._format_context(ctx) for ctx in contexts])
        # The system prompt enforces source-only answering to reduce hallucinations;
        # the guidance block adds question-type-specific formatting instructions
        prompt = (
            "You are a precise research assistant.\n"
            "Answer using only the provided context.\n"
            "If the context is incomplete, say what is missing instead of guessing.\n"
            "When sources disagree or are partial, say that explicitly.\n"
            "Use concise paragraphs or bullets when helpful.\n"
            f"{guidance}\n\n"
            f"Question: {question}\n\n"
            f"Context:\n{context_text}\n\n"
            "Answer:"
        )

        try:
            if self.settings.llm_provider == "groq":
                return self._generate_with_groq(prompt)
            return self._generate_with_ollama(prompt)
        except Exception:
            # Return a human-readable error instead of raising so the orchestrator
            # can still persist the failed response to chat history
            if self.settings.llm_provider == "groq":
                return "Groq is unavailable. Ensure GROQ_API_KEY and GROQ_MODEL are set correctly."
            return "Ollama is unavailable. Ensure Ollama is running and llama3 is pulled."

    def _build_guidance(self, question: str) -> str:
        """
        Select intent-specific formatting instructions to append to the system prompt.

        Inspects the question for structural keywords (steps, methods, summary) and
        returns targeted guidance that shapes the LLM's output format. This improves
        answer quality without requiring a separate intent classification call.

        Args:
            question (str): The user's question text.

        Returns:
            str: A one or two sentence guidance string inserted into the prompt,
            or a generic fallback if no specific intent is detected.
        """
        question_lower = question.lower()

        if any(phrase in question_lower for phrase in ["about the document", "about this document"]):
            return (
                "Summarize the document in exactly 4 concise bullet points covering the topic, "
                "goal, method, and conclusion when available."
            )

        if any(token in question_lower for token in ["step", "steps", "process", "pipeline"]):
            return (
                "List the steps described in the document in order. "
                "If the exact steps are not fully stated, say that clearly and provide only the steps that are explicit."
            )

        if any(token in question_lower for token in ["approach", "approaches", "method", "methodology"]):
            return (
                "Focus on the methods or approaches described in the document. "
                "Name each approach clearly and briefly explain its role. "
                "Do not add unrelated models."
            )

        if any(token in question_lower for token in ["summary", "summarize", "overview"]):
            return "Provide a short structured summary of the main ideas from the document in 4-5 lines."

        return "Answer directly and include the most relevant supporting details from the available sources."

    def _format_context(self, context: dict) -> str:
        """
        Serialize a single context dict into the plain-text format injected into the LLM prompt.

        Each context block is formatted with clearly labeled fields so the LLM can
        distinguish source types (rag, arxiv, ddg) and attribute claims correctly.

        Args:
            context (dict): Normalized context dict with keys: type, source/title,
                text, and optionally published_at, pdf_url, and link.

        Returns:
            str: Multi-line string block representing one source in the prompt context section.
        """
        parts = [f"Source Type: {context.get('type', 'unknown')}"]

        source = context.get("source") or context.get("title") or "unknown"
        parts.append(f"Source: {source}")

        published_at = context.get("published_at")
        if published_at:
            parts.append(f"Published: {published_at}")

        link = context.get("pdf_url") or context.get("link")
        if link:
            parts.append(f"Link: {link}")

        parts.append(str(context.get("text", "")).strip())
        return "\n".join(part for part in parts if part.strip())

    def _generate_with_ollama(self, prompt: str) -> str:
        """
        Call the local Ollama server to generate an answer.

        Temperature is set to 0.1 to keep answers deterministic and close to the
        evidence. num_predict caps the output length to avoid verbose responses.

        Args:
            prompt (str): The fully assembled prompt string including context and question.

        Returns:
            str: The content field from the Ollama chat response, stripped of whitespace.

        Raises:
            Exception: If Ollama is not running or the model has not been pulled.
        """
        response = self.client.chat(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            # Low temperature for factual, source-grounded responses
            options={"temperature": 0.1, "num_predict": 140},
        )
        return response["message"]["content"].strip()

    def _generate_with_groq(self, prompt: str) -> str:
        """
        Call the Groq cloud API (Llama 3) to generate an answer via HTTP.

        Uses httpx for synchronous HTTP because the orchestrator's ask_question
        method is synchronous. The 60-second timeout accounts for cold-start latency
        on the Groq API under high load.

        Args:
            prompt (str): The fully assembled prompt string including context and question.

        Returns:
            str: The content field from the first Groq chat completion choice,
            stripped of whitespace, or a configuration error message if the API key
            is missing.

        Raises:
            httpx.HTTPStatusError: If Groq returns a non-2xx response (e.g. 401, 429).
        """
        if not self.settings.groq_api_key:
            return "Groq is not configured. Set GROQ_API_KEY in your .env file."

        response = httpx.post(
            self.settings.groq_base_url,
            headers={
                "Authorization": f"Bearer {self.settings.groq_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.settings.groq_model,
                "messages": [{"role": "user", "content": prompt}],
                # Low temperature for consistent, source-grounded answers
                "temperature": 0.1,
                "max_tokens": 220,
            },
            timeout=60.0,
        )
        response.raise_for_status()
        payload = response.json()
        return payload["choices"][0]["message"]["content"].strip()
