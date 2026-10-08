"""Maps the many spellings of a test name to one canonical name (e.g. 'HB A1C' -> 'HbA1c').

The original text from the report is always kept separately by the parser.
"""
import re
from dataclasses import dataclass

from app.services.parameter_catalog import PARAMETERS, ParameterInfo


@dataclass
class AliasMatch:
    info: ParameterInfo
    end: int  # index in the line where the matched name ends


def _alias_to_regex(alias: str) -> str:
    """'free t3' -> 'free[\\s\\-]*t3' so spacing/hyphen differences still match."""
    tokens = [re.escape(t) for t in re.split(r"[\s\-]+", alias.strip()) if t]
    return r"[\s\-]*".join(tokens)


def _build_index() -> list[tuple[re.Pattern, ParameterInfo, int]]:
    entries = []
    for info in PARAMETERS:
        for alias in info.aliases:
            # \b-style guard: the name must not continue with another letter (so 'Hb' won't match 'HbA1c')
            pattern = re.compile(rf"^{_alias_to_regex(alias)}(?![A-Za-z])", re.IGNORECASE)
            entries.append((pattern, info, len(alias)))
    # Longest alias first so 'Hemoglobin A1c' wins over 'Hemoglobin'.
    entries.sort(key=lambda e: -e[2])
    return entries


_INDEX = _build_index()


def match_parameter_name(line: str, context: str = "blood") -> AliasMatch | None:
    """Find a known test name at the start of `line`. `context` is 'blood' or 'urine'
    (urine-only names like 'Protein' only match inside a urine section)."""
    # Inside a urine section, generic names like 'Glucose' / 'RBC' mean the urine versions,
    # so urine entries are tried first. Outside it, urine-only entries are never used.
    wanted_order = ("urine", "blood") if context == "urine" else ("blood",)
    for wanted in wanted_order:
        for pattern, info, _ in _INDEX:
            if info.context != wanted:
                continue
            m = pattern.match(line)
            if m:
                return AliasMatch(info, m.end())
    return None
