"""PDF handling: extract selectable text, or render pages to images for OCR."""
import io

import pypdf
import pypdfium2 as pdfium
from PIL import Image

from app.core.errors import UnreadableReportError

# If a PDF yields fewer non-space characters than this, we treat it as scanned.
MIN_TEXT_CHARS = 40
MAX_PAGES = 15              # pages rendered for OCR (slow)
MAX_TEXT_PAGES = 60        # pages whose text layer is read (fast)


def extract_pdf_text(content: bytes) -> str:
    """Return the selectable text of the PDF ('' if it is a scan with no text layer)."""
    try:
        reader = pypdf.PdfReader(io.BytesIO(content))
        if reader.is_encrypted:
            raise UnreadableReportError("This PDF is password protected. Please upload an unlocked copy.")
        pages = [(page.extract_text() or "") for page in reader.pages[:MAX_TEXT_PAGES]]
    except UnreadableReportError:
        raise
    except Exception:
        raise UnreadableReportError() from None
    return "\n".join(pages)


def extract_pdf_text_visual(content: bytes) -> str:
    """The text layer read in the order a person sees it (pdfium). Laboratory tables often come out in a different column order than
    with extract_pdf_text(), so the report is read both ways. Never raises: '' when it cannot be read."""
    try:
        pdf = pdfium.PdfDocument(content)
        return "\n".join(pdf[i].get_textpage().get_text_range() for i in range(min(len(pdf), MAX_TEXT_PAGES)))
    except Exception:
        return ""


def extract_pdf_text_layout(content: bytes) -> str:
    """The text layer with the page layout kept (each printed row stays on one line). Some laboratory PDFs store the test names and the
    values in separate blocks, which only this reading puts back together. Never raises: '' when it cannot be read."""
    try:
        reader = pypdf.PdfReader(io.BytesIO(content))
        return "\n".join((page.extract_text(extraction_mode="layout") or "") for page in reader.pages[:MAX_TEXT_PAGES])
    except Exception:
        return ""


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
