import os
from io import BytesIO
from importlib.util import find_spec
from shutil import which

from config import get_settings


class OCRUnavailableError(Exception):
    pass


class PDFOCRService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.tesseract_cmd = os.getenv("TESSERACT_CMD", "").strip() or None

    def _tesseract_available(self) -> bool:
        if self.tesseract_cmd:
            return os.path.isfile(self.tesseract_cmd) or which(self.tesseract_cmd) is not None
        return which("tesseract") is not None

    def is_available(self) -> bool:
        return (
            find_spec("fitz") is not None
            and find_spec("pytesseract") is not None
            and find_spec("PIL") is not None
            and self._tesseract_available()
        )

    def unavailable_reason(self) -> str:
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
        if not self.is_available():
            raise OCRUnavailableError(self.unavailable_reason())

        import fitz
        import pytesseract
        from PIL import Image

        if self.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd

        pages: list[str] = []
        document = fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            for page_index, page in enumerate(document):
                if page_index >= self.settings.ocr_max_pages:
                    break

                pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                image = Image.open(BytesIO(pixmap.tobytes("png")))
                text = pytesseract.image_to_string(image).strip()
                if text:
                    pages.append(text)
        finally:
            document.close()

        return "\n".join(pages).strip()
