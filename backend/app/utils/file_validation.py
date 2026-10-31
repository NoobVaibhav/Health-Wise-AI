"""Validate an uploaded file: extension, size and real content type (magic bytes)."""
import re
from pathlib import Path

from app.core.errors import FileTooLargeError, UnreadableReportError, UnsupportedFileError

ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png", "txt", "csv"}     # PDF, PNG and JPG are the normal reports; plain text and CSV are kept for lab exports
IMAGE_TYPES = {"jpg", "jpeg", "png"}
ALLOWED_TEXT = "PDF, PNG or JPG (a plain text or CSV export is also accepted), up to 10 MB"
MAX_FILENAME = 150


def safe_filename(name: str | None) -> str:
    """The name shown to people: no folder part, no control characters or markup, no odd symbols, at most 150 characters (the extension is kept)."""
    base = re.split(r"[\\/]", name or "")[-1]
    base = re.sub(r"[\x00-\x1f\x7f<>:\"|?*]", "", base)
    base = re.sub(r"\s+", " ", base).strip(" .")
    if not base or base.startswith("."):
        base = ("report" + base) if base.startswith(".") else "report"
    if len(base) > MAX_FILENAME:
        stem, dot, ext = base.rpartition(".")
        base = (stem[: MAX_FILENAME - len(ext) - 1] + "." + ext) if dot and len(ext) <= 8 else base[:MAX_FILENAME]
    return base


def get_extension(filename: str) -> str:
    return Path(filename).suffix.lower().lstrip(".")


def detect_file_type(filename: str, content: bytes) -> str:
    """Return 'pdf', 'image', 'text' after checking that the bytes match the extension.
    A renamed file (e.g. a .exe called report.pdf) is rejected here."""
    ext = get_extension(filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise UnsupportedFileError()

    if ext == "pdf":
        if not content.startswith(b"%PDF"):
            raise UnsupportedFileError("This file is not a valid PDF.")
        return "pdf"

    if ext in IMAGE_TYPES:
        is_jpeg = content.startswith(b"\xff\xd8\xff")
        is_png = content.startswith(b"\x89PNG\r\n\x1a\n")
        if not (is_jpeg or is_png):
            raise UnsupportedFileError("This file is not a valid PNG or JPG image.")
        if (ext == "png") != is_png:
            raise UnsupportedFileError("The file type does not match its name. Please choose a real PNG or JPG file.")
        return "image"

    # txt / csv: must be readable text
    try:
        content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            content.decode("latin-1")
        except UnicodeDecodeError:
            raise UnreadableReportError() from None
    return "text"


def validate_size(content: bytes, max_bytes: int) -> None:
    if len(content) == 0:
        raise UnreadableReportError("The uploaded file is empty.")
    if len(content) > max_bytes:
        raise FileTooLargeError(f"The file is too large. Maximum size is {max_bytes // (1024 * 1024)} MB.")
