import httpx
import ollama

from backend.config import get_settings


class AnswerGenerationAgent:
    def __init__(self) -> None:
        settings = get_settings()
        self.settings = settings
        self.model = settings.ollama_model
        self.client = ollama.Client(host=settings.ollama_base_url)

    def generate_answer(self, question: str, contexts: list[dict]) -> str:
        if not contexts:
            return "I could not find relevant context in uploaded documents."

        guidance = self._build_guidance(question)
        context_text = "\n\n".join([self._format_context(ctx) for ctx in contexts])
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
            if self.settings.llm_provider == "groq":
                return "Groq is unavailable. Ensure GROQ_API_KEY and GROQ_MODEL are set correctly."
            return "Ollama is unavailable. Ensure Ollama is running and llama3 is pulled."

    def _build_guidance(self, question: str) -> str:
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
        response = self.client.chat(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.1, "num_predict": 140},
        )
        return response["message"]["content"].strip()

    def _generate_with_groq(self, prompt: str) -> str:
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
                "temperature": 0.1,
                "max_tokens": 220,
            },
            timeout=60.0,
        )
        response.raise_for_status()
        payload = response.json()
        return payload["choices"][0]["message"]["content"].strip()
