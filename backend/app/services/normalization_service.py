"""Maps the many spellings of a test name to one canonical name (e.g. 'HB A1C' -> 'HbA1c').

The original text from the report is always kept separately by the parser.

Three things make the matching tolerant (each one is general, none is specific to one laboratory):
1. A name may contain commas, hyphens and slashes: "LDL / HDL", "Total Cholesterol/HDL", "Hematocrit Value, Hct".
2. A leading specimen word is optional: "Serum Triiodothyronine" is matched as "Triiodothyronine" unless a longer catalogue alias fits better
   ("Serum Bilirubin (Direct)" is the Direct bilirubin, not the plain bilirubin).
3. British and American spellings are both accepted (haemoglobin / hemoglobin, leucocyte / leukocyte).
"""
import re
from dataclasses import dataclass
from functools import cache

from app.services.parameter_catalog import PARAMETERS, ParameterInfo

# a laboratory often prints "Test name, ABBREVIATION" or "Test name ABBREVIATION"; the separators between the words of a name
NAME_SEPARATOR = r"[\s,\-]*"
SPECIMEN_PREFIX = re.compile(r"^(?:serum|plasma|blood|whole\s+blood|s\.)\s+", re.IGNORECASE)
# American <-> British spellings, tried as extra aliases
SPELLING_PAIRS = [("hemo", "haemo"), ("hema", "haema"), ("leuk", "leuc"), ("foetal", "fetal")]


@dataclass
class AliasMatch:
    info: ParameterInfo
    end: int  # index in the line where the matched name ends


def _alias_to_regex(alias: str) -> str:
    """'free t3' -> 'free[\\s,\\-]*t3'; 'ldl/hdl' -> 'ldl\\s*/\\s*hdl' (spacing around a slash, hyphens and commas do not matter)."""
    tokens = [t for t in re.split(r"[\s,\-]+", alias.strip()) if t]
    words = [r"\s*/\s*".join(re.escape(part) for part in token.split("/")) for token in tokens]
    return NAME_SEPARATOR.join(words)


def _spelling_variants(alias: str) -> set[str]:
    variants = {alias}
    for american, british in SPELLING_PAIRS:
        for form in tuple(variants):
            if american in form:
                variants.add(form.replace(american, british))
            if british in form:
                variants.add(form.replace(british, american))
    return variants


def _build_index() -> list[tuple[re.Pattern, ParameterInfo, int]]:
    entries = []
    for info in PARAMETERS:
        for alias in {variant for a in info.aliases for variant in _spelling_variants(a)}:
            # \b-style guard: the name must not continue with another letter (so 'Hb' won't match 'HbA1c')
            pattern = re.compile(rf"^{_alias_to_regex(alias)}(?![A-Za-z])", re.IGNORECASE)
            entries.append((pattern, info, len(alias)))
    # Longest alias first so 'Hemoglobin A1c' wins over 'Hemoglobin'.
    entries.sort(key=lambda e: -e[2])
    return entries


_INDEX = _build_index()


def _match_start(line: str, context: str) -> AliasMatch | None:
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


def match_parameter_name(line: str, context: str = "blood") -> AliasMatch | None:
    """Find a known test name at the start of `line`. `context` is 'blood' or 'urine'
    (urine-only names like 'Protein' only match inside a urine section).
    The line is read as printed and also without a leading specimen word ('Serum', 'Plasma' ...); the reading that
    consumes more of the line wins, so the most specific name is chosen. When both end at the same place, the printed one wins."""
    printed = _match_start(line, context)
    prefix = SPECIMEN_PREFIX.match(line)
    if not prefix:
        return printed
    bare = _match_start(line[prefix.end():], context)
    if bare is None:
        return printed
    bare = AliasMatch(bare.info, bare.end + prefix.end())
    return bare if printed is None or bare.end > printed.end else printed


@cache
def _own_names(name: str) -> re.Pattern | None:
    info = next((p for p in PARAMETERS if p.name == name), None)
    if info is None:
        return None
    aliases = sorted({variant for a in info.aliases for variant in _spelling_variants(a)}, key=len, reverse=True)
    body = "|".join(_alias_to_regex(a) for a in aliases)
    return re.compile(rf"^[\s,:(\-]*(?:{body})\)?(?![A-Za-z])", re.IGNORECASE)


def skip_own_names(info: ParameterInfo, line: str, end: int) -> int:
    """Laboratories print "Mean Corpuscular Volume, MCV" or "Hematocrit Value Hct": the abbreviation after the full name is another name of the SAME test,
    not part of the result. Returns the position after the printed name and its own abbreviations."""
    pattern = _own_names(info.name)
    while pattern is not None:
        m = pattern.match(line[end:])
        if not m or m.end() == 0:
            break
        end += m.end()
    return end
