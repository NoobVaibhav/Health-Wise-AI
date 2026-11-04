"""Clean raw extracted/OCR text so the parser sees consistent characters."""
import re
import unicodedata

_DASHES = dict.fromkeys(map(ord, "–—−‒‐"), "-")


def clean_text(raw: str, is_csv: bool = False, keep_columns: bool = False) -> str:
    """keep_columns=True leaves runs of spaces alone: the table reader (report_rows.py) needs them, because cells are separated by two or more spaces."""
    text = unicodedata.normalize("NFKC", raw)
    text = text.translate(_DASHES)                      # en/em dash -> '-'
    text = text.replace("μ", "µ")                       # Greek mu -> micro sign (units like uIU/mL)
    text = re.sub(r"\ufffd(?=(?:IU|g|mol|L)\b)", "µ", text)   # a micro sign the PDF font could not map ("replacement-character IU/mL") -> µ
    text = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", text)    # zero-width characters
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if is_csv:
        text = text.replace(",", "  ").replace(";", "  ").replace("\t", "  ")
    text = text.replace("|", " ")                       # table borders from OCR
    if not is_csv:
        text = re.sub(r"(?<=\d),(?=\d{1,2}(?![\d,]))", ".", text)   # decimal comma "5,6" -> "5.6" ("1,200" and Indian "1,50,000" are thousands separators, so they are left alone)
    text = re.sub(r"(?<=[A-Za-z]),[ \t]*(?=[A-Za-z(])", " ", text)  # "BILIRUBIN, TOTAL" -> "BILIRUBIN TOTAL" (not 1,000)
    if keep_columns:
        lines = [line.replace("\t", "    ").rstrip() for line in text.split("\n")]
    else:
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line.strip())
