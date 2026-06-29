# document_processing_agent.py
# PDF text extraction and chunking agent for the MARKA document ingestion pipeline.
# Handles the first two stages of ingestion: extracting raw text from a PDF
# (with OCR fallback for scanned documents) and splitting it into overlapping
# chunks that the EmbeddingAgent will encode into vectors.

# BytesIO wraps raw PDF bytes for in-memory reading without a temp file
from io import BytesIO

# FastAPI UploadFile for the async file read in extract_text
from fastapi import UploadFile

# LangChain text splitter for overlap-aware chunking; imported with a fallback
# to handle offline environments where langchain_text_splitters is unavailable
try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except Exception:  # pragma: no cover - fallback for offline environments
    RecursiveCharacterTextSplitter = None

# pypdf error type for structured handling of corrupt or invalid PDFs
from pypdf.errors import PdfReadError
from pypdf import PdfReader

# Application settings (OCR enabled flag, max pages)
from backend.config import get_settings
# OCR service and its unavailability sentinel exception
from backend.services.pdf_service import OCRUnavailableError, PDFOCRService


class DocumentExtractionError(Exception):
    """
    Raised when a PDF cannot be parsed, is encrypted, or yields no extractable text.

    Caught by the orchestrator and re-raised as an HTTPException 400 so the
    frontend can display a clear error message to the user.
    """
    pass


class DocumentProcessingAgent:
    """
    PDF ingestion agent responsible for text extraction and semantic chunking.

    Stage 1 - Extraction:
        Reads the PDF using pypdf for text-based PDFs. If pypdf produces no text
        (scanned or image-only PDFs), and OCR is enabled in settings, falls back
        to PyMuPDF + Tesseract via PDFOCRService.

    Stage 2 - Chunking:
        Splits extracted text into overlapping chunks using LangChain's
        RecursiveCharacterTextSplitter (chunk_size=900, overlap=150). If LangChain
        is unavailable, falls back to a custom character-level splitter that
        respects word boundaries.

    Attributes:
        settings: Parsed application settings (OCR enabled flag, Tesseract path).
        chunk_size (int): Target character count per chunk. Minimum 100.
        chunk_overlap (int): Character overlap between consecutive chunks. Capped
            at chunk_size - 1 to prevent infinite loops.
        splitter: LangChain RecursiveCharacterTextSplitter instance, or None if
            LangChain is unavailable.
        ocr_service (PDFOCRService): OCR service that wraps PyMuPDF + Tesseract.
    """

    def __init__(self, chunk_size: int = 900, chunk_overlap: int = 150) -> None:
        self.settings = get_settings()
        # Enforce minimum chunk_size so each chunk contains enough context for the LLM
        self.chunk_size = max(100, int(chunk_size))
        # Cap overlap at chunk_size - 1 to prevent the fallback splitter from looping
        self.chunk_overlap = max(0, min(int(chunk_overlap), self.chunk_size - 1))
        if RecursiveCharacterTextSplitter is not None:
            self.splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size, chunk_overlap=self.chunk_overlap
            )
        else:
            self.splitter = None
        self.ocr_service = PDFOCRService()

    async def extract_text(self, file: UploadFile) -> str:
        """
        Extract plain text from an uploaded PDF file.

        Validates the file before parsing (extension, MIME type, magic bytes),
        then attempts pypdf text extraction. Falls back to OCR if pypdf returns
        an empty string and OCR is enabled in application settings.

        Args:
            file (UploadFile): Multipart PDF upload received from the FastAPI route.
                The file is read fully into memory; it is not streamed.

        Returns:
            str: Extracted plain text content, stripped of leading/trailing whitespace.
            Returns an empty string only if OCR is disabled and pypdf found no text.

        Raises:
            DocumentExtractionError: For any of the following conditions:
                - File extension is not .pdf
                - MIME type is not application/pdf
                - File bytes are empty
                - File does not begin with the PDF magic bytes (%PDF-)
                - PDF is corrupt or cannot be parsed by pypdf
                - PDF is encrypted and cannot be decrypted with an empty password
                - OCR is attempted but all required dependencies are missing
                - OCR processing fails for any other reason
        """
        filename = (file.filename or "").lower()
        content_type = (file.content_type or "").lower()

        if filename and not filename.endswith(".pdf"):
            raise DocumentExtractionError("Only PDF files are supported.")

        if content_type and content_type not in {"application/pdf", "application/x-pdf"}:
            raise DocumentExtractionError("Uploaded file is not marked as a PDF.")

        data = await file.read()
        if not data:
            raise DocumentExtractionError("Uploaded PDF is empty.")

        # Validate the PDF magic bytes before attempting to parse; this catches
        # files with a .pdf extension that are actually images or other formats
        if not data.startswith(b"%PDF-"):
            raise DocumentExtractionError("Uploaded file does not look like a valid PDF.")

        try:
            # strict=False tolerates minor PDF specification violations common in
            # PDFs exported from third-party tools
            reader = PdfReader(BytesIO(data), strict=False)
        except PdfReadError as exc:
            raise DocumentExtractionError("Invalid or corrupted PDF file.") from exc
        except Exception as exc:
            raise DocumentExtractionError("PDF could not be parsed.") from exc

        if reader.is_encrypted:
            try:
                # Attempt decryption with an empty password (covers owner-password-only PDFs)
                reader.decrypt("")
            except Exception as exc:
                raise DocumentExtractionError("Encrypted PDFs are not supported.") from exc

        pages = []
        for page in reader.pages:
            try:
                pages.append(page.extract_text() or "")
            except Exception:
                # Skip individual pages that fail to extract rather than aborting the whole file
                pages.append("")

        extracted_text = "\n".join(pages).strip()
        if extracted_text:
            return extracted_text

        # pypdf returned empty text: the PDF is likely scanned or image-only
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
        """
        Split extracted text into overlapping chunks for vector embedding.

        Uses LangChain's RecursiveCharacterTextSplitter when available, which
        splits on semantic boundaries (paragraphs, sentences, spaces) before
        falling back to raw character splits. Falls back to a custom splitter
        if LangChain is not installed.

        Args:
            text (str): The full extracted text from the PDF.

        Returns:
            list[str]: List of text chunks. Empty list if the input is empty.
        """
        if not text:
            return []
        if self.splitter is not None:
            return self.splitter.split_text(text)
        return self._fallback_split(text)

    def _fallback_split(self, text: str) -> list[str]:
        # Simple character-based chunking with overlap for offline installs.
        # Attempts to break at a word boundary by searching backwards from the
        # chunk boundary for the last space within a 200-character window.
        chunks: list[str] = []
        text_length = len(text)
        start = 0
        while start < text_length:
            end = min(start + self.chunk_size, text_length)
            if end < text_length:
                window = text[start:end]
                last_space = window.rfind(" ")
                # Only snap to the space boundary if it is close to the target end,
                # to avoid creating very short chunks on space-dense text
                if last_space > max(0, len(window) - 200):
                    end = start + last_space
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end >= text_length:
                break
            # Advance start by (chunk_size - overlap) to maintain the overlap window
            start = max(0, end - self.chunk_overlap)
            if start <= 0 and end == text_length:
                break
        return chunks
