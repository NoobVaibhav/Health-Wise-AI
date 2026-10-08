"""Clean raw extracted/OCR text so the parser sees consistent characters."""
import re
import unicodedata

_DASHES = dict.fromkeys(map(ord, "–—−‒‐"), "-")


def clean_text(raw: str, is_csv: bool = False) -> str:
    text = unicodedata.normalize("NFKC", raw)
    text = text.translate(_DASHES)                      # en/em dash -> '-'
    text = text.replace("μ", "µ")             # Greek mu -> micro sign (units like uIU/mL)
    text = re.sub(r"[​‌‍﻿]", "", text)  # zero-width characters
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if is_csv:
        text = text.replace(",", "  ").replace(";", "  ").replace("\t", "  ")
    text = text.replace("|", " ")                       # table borders from OCR
    text = re.sub(r"(?<=[A-Za-z]),[ 	]*(?=[A-Za-z(])", " ", text)  # "BILIRUBIN, TOTAL" -> "BILIRUBIN TOTAL" (not 1,000)
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line)
