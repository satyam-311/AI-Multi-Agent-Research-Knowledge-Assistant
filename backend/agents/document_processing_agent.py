from io import BytesIO

from fastapi import UploadFile
try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except Exception:  # pragma: no cover - fallback for offline environments
    RecursiveCharacterTextSplitter = None
from pypdf.errors import PdfReadError
from pypdf import PdfReader

from backend.config import get_settings
from backend.services.pdf_service import OCRUnavailableError, PDFOCRService


class DocumentExtractionError(Exception):
    pass


class DocumentProcessingAgent:
    def __init__(self, chunk_size: int = 900, chunk_overlap: int = 150) -> None:
        self.settings = get_settings()
        self.chunk_size = max(100, int(chunk_size))
        self.chunk_overlap = max(0, min(int(chunk_overlap), self.chunk_size - 1))
        if RecursiveCharacterTextSplitter is not None:
            self.splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size, chunk_overlap=self.chunk_overlap
            )
        else:
            self.splitter = None
        self.ocr_service = PDFOCRService()

    async def extract_text(self, file: UploadFile) -> str:
        filename = (file.filename or "").lower()
        content_type = (file.content_type or "").lower()

        if filename and not filename.endswith(".pdf"):
            raise DocumentExtractionError("Only PDF files are supported.")

        if content_type and content_type not in {"application/pdf", "application/x-pdf"}:
            raise DocumentExtractionError("Uploaded file is not marked as a PDF.")

        data = await file.read()
        if not data:
            raise DocumentExtractionError("Uploaded PDF is empty.")

        if not data.startswith(b"%PDF-"):
            raise DocumentExtractionError("Uploaded file does not look like a valid PDF.")

        try:
            reader = PdfReader(BytesIO(data), strict=False)
        except PdfReadError as exc:
            raise DocumentExtractionError("Invalid or corrupted PDF file.") from exc
        except Exception as exc:
            raise DocumentExtractionError("PDF could not be parsed.") from exc

        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception as exc:
                raise DocumentExtractionError("Encrypted PDFs are not supported.") from exc

        pages = []
        for page in reader.pages:
            try:
                pages.append(page.extract_text() or "")
            except Exception:
                pages.append("")

        extracted_text = "\n".join(pages).strip()
        if extracted_text:
            return extracted_text

        if not self.settings.ocr_fallback_enabled:
            return ""

        try:
            return self.ocr_service.extract_text(data)
        except OCRUnavailableError as exc:
            raise DocumentExtractionError(
                "No extractable text found in PDF. "
                f"{exc} Install PyMuPDF, Pillow, pytesseract, and the Tesseract OCR engine for scanned PDFs. "
                "If Tesseract is installed but not on PATH, set TESSERACT_CMD to the tesseract.exe path."
            ) from exc
        except Exception as exc:
            raise DocumentExtractionError("OCR fallback failed while processing the PDF.") from exc

    def chunk_text(self, text: str) -> list[str]:
        if not text:
            return []
        if self.splitter is not None:
            return self.splitter.split_text(text)
        return self._fallback_split(text)

    def _fallback_split(self, text: str) -> list[str]:
        # Simple character-based chunking with overlap for offline installs.
        chunks: list[str] = []
        text_length = len(text)
        start = 0
        while start < text_length:
            end = min(start + self.chunk_size, text_length)
            if end < text_length:
                window = text[start:end]
                last_space = window.rfind(" ")
                if last_space > max(0, len(window) - 200):
                    end = start + last_space
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end >= text_length:
                break
            start = max(0, end - self.chunk_overlap)
            if start <= 0 and end == text_length:
                break
        return chunks
