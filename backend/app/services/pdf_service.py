"""PDF handling: extract selectable text, or render pages to images for OCR."""
import io

import pypdf
import pypdfium2 as pdfium
from PIL import Image

from app.core.errors import UnreadableReportError

# If a PDF yields fewer non-space characters than this, we treat it as scanned.
MIN_TEXT_CHARS = 40
MAX_PAGES = 15


def extract_pdf_text(content: bytes) -> str:
    """Return the selectable text of the PDF ('' if it is a scan with no text layer)."""
    try:
        reader = pypdf.PdfReader(io.BytesIO(content))
        if reader.is_encrypted:
            raise UnreadableReportError("This PDF is password protected. Please upload an unlocked copy.")
        pages = [(page.extract_text() or "") for page in reader.pages[:MAX_PAGES]]
    except UnreadableReportError:
        raise
    except Exception:
        raise UnreadableReportError() from None
    return "\n".join(pages)


def has_enough_text(text: str) -> bool:
    return len("".join(text.split())) >= MIN_TEXT_CHARS


def render_pdf_pages(content: bytes, scale: float = 2.5) -> list[Image.Image]:
    """Render each PDF page to a PIL image (used when OCR is needed)."""
    try:
        pdf = pdfium.PdfDocument(content)
        images = []
        for index in range(min(len(pdf), MAX_PAGES)):
            images.append(pdf[index].render(scale=scale).to_pil())
        return images
    except Exception:
        raise UnreadableReportError() from None
