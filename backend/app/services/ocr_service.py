"""OCR using Tesseract (via pytesseract). Tesseract itself must be installed separately."""
import io

import pytesseract
from PIL import Image, ImageFilter, ImageOps, UnidentifiedImageError

from app.core.config import get_settings
from app.core.errors import OCRUnavailableError, UnreadableReportError


def _configure_tesseract() -> None:
    cmd = get_settings().tesseract_cmd
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd


def ocr_is_available() -> bool:
    _configure_tesseract()
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def load_image(content: bytes) -> Image.Image:
    try:
        image = Image.open(io.BytesIO(content))
        image.load()
        return image
    except (UnidentifiedImageError, OSError):
        raise UnreadableReportError() from None


def preprocess_image(image: Image.Image) -> Image.Image:
    """Make the image easier for OCR: grayscale, upscale small images, boost contrast, denoise."""
    image = ImageOps.exif_transpose(image).convert("L")
    if image.width < 1600:
        factor = 1600 / image.width
        image = image.resize((int(image.width * factor), int(image.height * factor)), Image.LANCZOS)
    image = ImageOps.autocontrast(image)
    return image.filter(ImageFilter.MedianFilter(size=3))


def run_ocr(images: list[Image.Image]) -> str:
    """OCR a list of page images and join the text."""
    if not ocr_is_available():
        raise OCRUnavailableError()
    texts = []
    for image in images:
        # psm 6 = "assume a single uniform block of text", works well for lab tables
        texts.append(pytesseract.image_to_string(preprocess_image(image), config="--psm 6"))
    return "\n".join(texts)
