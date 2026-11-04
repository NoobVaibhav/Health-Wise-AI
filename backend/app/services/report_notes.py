"""The interpretation table some laboratories print under a panel, read as a SEPARATE note.

Example (lipid profile): "LDL: Optimal <100, Near Optimal 100-129, Borderline High 130-159, High 160-189, Very High >190".
A result's STATUS always comes from the reference range printed on its own row. This table can disagree with that range (LDL 36 is "Low" by the
printed range 85 - 130 while the table lists LDL below 100 as "Optimal"), so what the table says is shown next to the result as a note and never changes the status.

The table is read by column position: the header row names the tests (Total Cholesterol, HDL, LDL, Triglycerides) and each following row has one
"tier  limit" pair under each name. Only text that still has its column spacing can be read this way."""
import re
from dataclasses import dataclass

from app.services.normalization_service import match_parameter_name
from app.services.report_parser import NUMBER

TABLE_START = re.compile(r"^\s*interpre\w*\s*:?\s*$", re.IGNORECASE)
UNIT_CELL = re.compile(r"^\([A-Za-z/%µ0-9.^]+\)$")
TIER = re.compile(rf"^(?P<label>[A-Za-z][A-Za-z \-]*?)\s*(?P<cmp>[<>≤≥]=?)?\s*(?P<a>{NUMBER})(?:\s*-\s*(?P<b>{NUMBER}))?$")
TABLE_END = re.compile(r"page\s+\d+\s+of\s+\d+|patient(?:'s)?\s+name|^\s*(?:mr|mrs|ms|dr)\.|pathologist|incharge|end\s+of\s+report", re.IGNORECASE)
SLACK = 3               # columns of tolerance when a printed cell starts a little left of its heading


@dataclass
class Tier:
    label: str               # "Optimal", "Borderline High"
    low: float | None
    high: float | None
    comparator: str | None   # "<" ">" or None for a closed range
    unit: str | None = None

    def contains(self, value: float) -> bool:
        if self.comparator in ("<", "≤", "<="):
            return value < self.high if self.comparator == "<" else value <= self.high
        if self.comparator in (">", "≥", ">="):
            return value > self.low if self.comparator == ">" else value >= self.low
        return self.low <= value <= self.high

    def limit_text(self) -> str:
        if self.comparator in ("<", "≤", "<="):
            return f"below {self.high:g}"
        if self.comparator in (">", "≥", ">="):
            return f"above {self.low:g}"
        return f"{self.low:g}-{self.high:g}"


def _cells(line: str) -> list[tuple[int, str]]:
    return [(m.start(), m.group().strip()) for m in re.finditer(r"\S(?:(?!\s{2,}).)*", line)]


def _tier(text: str, unit: str | None) -> Tier | None:
    m = TIER.match(text.strip())
    if not m:
        return None
    a = float(m["a"].replace(",", ""))
    if m["b"]:
        return Tier(m["label"].strip(), a, float(m["b"].replace(",", "")), None, unit)
    if m["cmp"] and m["cmp"].startswith("<"):
        return Tier(m["label"].strip(), None, a, m["cmp"], unit)
    if m["cmp"] and m["cmp"].startswith(">"):
        return Tier(m["label"].strip(), a, None, m["cmp"], unit)
    return None


def _columns(header: list[tuple[int, str]], following: str | None) -> list[tuple[int, str, str | None]]:
    """[(start column, test name, unit)] from the header row; a name that wraps ("Total" / "Cholesterol") is joined."""
    columns: list[tuple[int, str, str | None]] = []
    for start, text in header:
        if UNIT_CELL.match(text) and columns:
            s, name, _ = columns[-1]
            columns[-1] = (s, name, text.strip("()"))
        elif not UNIT_CELL.match(text):
            columns.append((start, text, None))
    if following:
        extra = _cells(following)
        if len(extra) == 1:
            for i, (start, name, unit) in enumerate(columns):
                if abs(start - extra[0][0]) <= SLACK:
                    columns[i] = (start, f"{name} {extra[0][1]}", unit)
    return columns


def read_interpretation_tables(text: str) -> dict[str, list[Tier]]:
    """{canonical test name: [tiers]} from every "Interpretation" table whose header row names tests with units in brackets."""
    lines = text.splitlines()
    found: dict[str, list[Tier]] = {}
    for i, line in enumerate(lines):
        if not TABLE_START.match(line):
            continue
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        if j >= len(lines):
            continue
        header = _cells(lines[j])
        if sum(1 for _, t in header if UNIT_CELL.match(t)) < 1:
            continue
        columns = _columns(header, lines[j + 1] if j + 1 < len(lines) else None)
        tiers: list[list[Tier]] = [[] for _ in columns]
        pending: list[str | None] = [None] * len(columns)            # a tier label that wrapped onto the next line ("Borderline" / "High")
        for row in lines[j + 1:]:
            if TABLE_END.search(row):
                break
            if not row.strip():
                continue
            cells = _cells(row)
            if cells and cells[0][1] in {name.split()[-1] for _, name, _ in columns} and len(cells) == 1 and cells[0][0] <= columns[0][0] + SLACK:
                continue                                              # the wrapped second word of a test name ("Cholesterol")
            per_column: dict[int, list[str]] = {}
            for start, cell in cells:
                k = max((n for n, (cstart, _, _) in enumerate(columns) if start >= cstart - SLACK), default=0)
                per_column.setdefault(k, []).append(cell)
            for k, parts in per_column.items():
                joined = " ".join(parts)
                tier = _tier(joined, columns[k][2])
                if tier:
                    if pending[k]:
                        tier.label = f"{pending[k]} {tier.label}".strip() if not tier.label.lower().startswith(pending[k].lower()) else tier.label
                        pending[k] = None
                    tiers[k].append(tier)
                elif re.fullmatch(r"[A-Za-z][A-Za-z ]*", joined) and tiers[k]:
                    last = tiers[k][-1]
                    if last.label.lower() in ("borderline", "near", "very") or joined.lower() in ("high", "low"):
                        last.label = f"{last.label} {joined}"          # "Borderline" + "High" on the next line
        for (_, name, _), column_tiers in zip(columns, tiers):
            hit = match_parameter_name(name)
            if hit and column_tiers:
                found[hit.info.name] = column_tiers
    return found


def table_notes(tables: dict[str, list[Tier]], parameters: list) -> list[dict]:
    """One note for each result whose value falls in a tier of the report's own table. The status is NOT changed by the note."""
    notes = []
    for p in parameters:
        e = p.extracted
        for tier in tables.get(e.normalized_name, []):
            if tier.contains(e.value):
                unit = f" {tier.unit}" if tier.unit else ""
                printed = f" ({e.reference_text})" if e.reference_text else ""
                text = (f"The report's own interpretation table lists {e.normalized_name} {tier.limit_text()}{unit} as {tier.label}. "
                        f"This note is separate from the status, which comes from the range printed on the result row{printed}.")
                notes.append({"name": e.normalized_name, "value": e.value, "tier": tier.label, "limit": tier.limit_text(), "text": text})
                break
    return notes
