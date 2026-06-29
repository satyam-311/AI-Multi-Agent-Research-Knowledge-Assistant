# pdf_service.py
# OCR fallback service for the MARKA document ingestion pipeline.
# Called by DocumentProcessingAgent when pypdf extracts no text from a PDF,
# indicating the document is scanned or image-based. Uses PyMuPDF to render
# pages as images and Tesseract to extract text from those images.

import os
from io import BytesIO
# find_spec checks whether optional dependencies are installed without importing them
from importlib.util import find_spec
# which locates the Tesseract binary on the system PATH
from shutil import which

# Application settings for OCR configuration (max pages, enabled flag)
from backend.config import get_settings


class OCRUnavailableError(Exception):
    """
    Raised when OCR extraction is attempted but required dependencies are missing.

    Caught by DocumentProcessingAgent and re-raised as a DocumentExtractionError
    with installation instructions so the user receives actionable feedback.
    """
    pass


class PDFOCRService:
    """
    OCR service that extracts text from scanned PDF documents.

    Uses PyMuPDF (fitz) to render each PDF page as a 2x-upscaled PNG image,
    then passes each image to pytesseract (a Python wrapper for Tesseract OCR)
    to recognize the text. The 2x matrix scaling improves OCR accuracy on
    low-resolution scans.

    All dependencies (fitz, pytesseract, PIL, Tesseract binary) are checked at
    runtime via is_available() before any OCR call is attempted, so the main
    extraction path can fail fast with a clear error message.

    Attributes:
        settings: Parsed application settings (ocr_max_pages).
        tesseract_cmd (str | None): Path to the Tesseract binary from the
            TESSERACT_CMD environment variable, or None to use the system PATH.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        # Prefer an explicitly configured binary path over PATH resolution
        # to support Windows installs where Tesseract is not on PATH by default
        self.tesseract_cmd = os.getenv("TESSERACT_CMD", "").strip() or None

    def _tesseract_available(self) -> bool:
        """
        Check whether the Tesseract OCR binary is accessible.

        Checks the explicit TESSERACT_CMD path first (if set), then falls back
        to searching the system PATH via shutil.which.

        Returns:
            bool: True if the Tesseract binary can be found and executed.
        """
        if self.tesseract_cmd:
            # Accept both a direct file path and a command name resolvable via PATH
            return os.path.isfile(self.tesseract_cmd) or which(self.tesseract_cmd) is not None
        return which("tesseract") is not None

    def is_available(self) -> bool:
        """
        Check whether all OCR dependencies are installed and accessible.

        All four components must be present for OCR to function:
        - fitz (PyMuPDF): PDF-to-image rendering
        - pytesseract: Python wrapper for Tesseract
        - PIL (Pillow): Image handling between PyMuPDF and pytesseract
        - Tesseract binary: The actual OCR engine

        Returns:
            bool: True only when all four dependencies are available.
        """
        return (
            find_spec("fitz") is not None
            and find_spec("pytesseract") is not None
            and find_spec("PIL") is not None
            and self._tesseract_available()
        )

    def unavailable_reason(self) -> str:
        """
        Build a human-readable message listing all missing OCR dependencies.

        Called by DocumentProcessingAgent when OCR is needed but unavailable,
        to surface installation instructions in the API error response.

        Returns:
            str: A message naming each missing component, or a generic message
            if all components are present but the service is still unavailable.
        """
        missing = []
        if find_spec("fitz") is None:
            missing.append("PyMuPDF")
        if find_spec("pytesseract") is None:
            missing.append("pytesseract")
        if find_spec("PIL") is None:
            missing.append("Pillow")

        if not self._tesseract_available():
            if self.tesseract_cmd:
                missing.append(f"Tesseract OCR engine (TESSERACT_CMD={self.tesseract_cmd} not found)")
            else:
                missing.append("Tesseract OCR engine (tesseract not on PATH)")

        if missing:
            return f"OCR fallback is not installed ({', '.join(missing)} missing)."
        return "OCR fallback is unavailable."

    def extract_text(self, pdf_bytes: bytes) -> str:
        """
        Extract text from a scanned PDF using PyMuPDF page rendering and Tesseract OCR.

        Renders each page at 2x resolution to improve character recognition accuracy
        on low-DPI scans, then runs Tesseract on the resulting PNG image. Processing
        stops after ocr_max_pages pages to bound memory and CPU usage on large documents.

        Args:
            pdf_bytes (bytes): Raw PDF file bytes read from the uploaded file.

        Returns:
            str: Concatenated OCR output from all processed pages, stripped of
            leading/trailing whitespace. Empty pages contribute nothing to the result.

        Raises:
            OCRUnavailableError: If is_available() returns False, listing the missing
                dependencies so the caller can surface installation instructions.
        """
        if not self.is_available():
            raise OCRUnavailableError(self.unavailable_reason())

        # Import heavy dependencies inside the method to keep startup time fast
        # and to prevent ImportError at module load when the packages are missing
        import fitz
        import pytesseract
        from PIL import Image

        if self.tesseract_cmd:
            # Override pytesseract's default binary path with the configured one
            pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd

        pages: list[str] = []
        document = fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            for page_index, page in enumerate(document):
                if page_index >= self.settings.ocr_max_pages:
                    # Stop processing to avoid excessive CPU/memory on long documents
                    break

                # Matrix(2, 2) doubles both x and y resolution; higher DPI improves
                # Tesseract accuracy at the cost of more memory per page
                pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                image = Image.open(BytesIO(pixmap.tobytes("png")))
                text = pytesseract.image_to_string(image).strip()
                if text:
                    pages.append(text)
        finally:
            # Always close the fitz document to release the file handle
            document.close()

        return "\n".join(pages).strip()
