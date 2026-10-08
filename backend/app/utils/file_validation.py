"""Validate an uploaded file: extension, size and real content type (magic bytes)."""
from pathlib import Path

from app.core.errors import FileTooLargeError, UnreadableReportError, UnsupportedFileError

ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png", "webp", "txt", "csv"}
IMAGE_TYPES = {"jpg", "jpeg", "png", "webp"}


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
        is_webp = content[:4] == b"RIFF" and content[8:12] == b"WEBP"
        if not (is_jpeg or is_png or is_webp):
            raise UnsupportedFileError("This file is not a valid image.")
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
