"""Reads the printed ROWS of a report (test name, value, unit, reference range) and the section each row sits in.

This is a second, independent look at the report. The deterministic extractor (report_parser.py) reads the tests it knows and judges them against the
printed range. This module reads every printed result row, known or not, so that two things can be done honestly:
  - results of sections that are not blood panels (Widal, semen examination, Mantoux ...) can be shown exactly as printed, without a verdict;
  - the coverage check (report_coverage.py) can say which printed rows were NOT analysed.

It works on text that still has its column spacing (the page-layout reading of a PDF, or a plain text file): cells are separated by two or more spaces.
When the spacing is gone (OCR text), rows that end in a number can still be read; rows with a word as the result cannot, and the coverage check is
then less complete. Nothing here invents a value or a range: every field is cut out of the printed line.
"""
import re
from dataclasses import dataclass, field

from app.services.report_parser import NUMBER

# --- what is NOT a result row -----------------------------------------------------------------------------------------------
FURNITURE = re.compile(
    r"^\s*(?:(?:mr|mrs|ms|miss|dr|prof)\.|patient(?:'s)?\s+name|name\b|age\s*/\s*sex|age\b|sex\b|referred\s+by|ref(?:erred)?\.?\s*by|reg\.?\s*no|uhid|collected\s+on|reported\s+on|registered|"
    r"report(?:ed)?\s+(?:date|on|no)|test\s+date|date\s+of\s+\w+|dob|gender|doctor|consultant|hospital|lab\s*(?:no|id)|sample\s+(?:id|no|collected|date)|accession|bill|invoice|phone|mobile|address|date\b|page\s+\d+\s+of\s+\d+|~~~|\*\*\*|-{3,})"
    r"|\bpage\s+\d+\s+of\s+\d+\b|end\s+of\s+(?:the\s+)?report"
    r"|\b(?:pathologist|lab\s*incharge|technician|technologist|dmlt|mbbs|biochemist|microbiologist)\b",
    re.IGNORECASE)
TABLE_HEADER_WORDS = {"TEST", "TEST NAME", "INVESTIGATION", "VALUE", "RESULT", "RESULTS", "UNIT", "UNITS", "REFERENCE", "REFERENCE RANGE", "REFERENCE VALUE",
                      "NORMAL RANGE", "BIOLOGICAL REFERENCE", "BIO. REF. INTERVAL", "METHOD", "FLAG", "REMARK", "REMARKS"}
NOTES_HEADING = re.compile(r"^\s*(?:interpre\w*|comments?|notes?|remarks?|advice|clinical\s+significance|limitations?)\s*:?\s*$", re.IGNORECASE)
PLACEHOLDER = re.compile(r"<[A-Za-z][^<>]{1,60}>")                      # "<IMPRESSION>": a template field nobody filled in ("< 2" and "<100" are limits, not placeholders)
METADATA_KEYS = re.compile(r"^(?:method(?:ology)?|instrument|analy[sz]er|reference|ref|page|sample\s+type|specimen\s+type|kit|lot|batch|time|print\w*)$", re.IGNORECASE)

FLAG_CELL = re.compile(r"^(?:HH|LL|H|L|\*+|High|Low|Critical)$", re.IGNORECASE)
LIMIT = rf"(?:[<>≤≥]=?|up\s*to|upto)?\s*{NUMBER}"
REFERENCE_CELL = re.compile(rf"^\(?\s*{LIMIT}(?:\s*-\s*{NUMBER})?\s*\)?$|^(?:negative|nil|absent|non[- ]?reactive|not\s+detected)$", re.IGNORECASE)
NUMERIC_VALUE = re.compile(rf"^[<>]?\s*{NUMBER}$")
RATIO_VALUE = re.compile(r"^\d+\s*:\s*\d+$")                              # titres such as 1:20
VALUE_WITH_UNIT = re.compile(rf"^({NUMBER})\s*([A-Za-z%/µ][A-Za-z%/µ0-9.^]*)$")        # "06mm", "72 hrs"
VALUE_UNIT_RANGE = re.compile(rf"^(?P<num>{NUMBER})\s*(?P<unit>[A-Za-z%/µ][A-Za-z%/µ0-9.^]*)?\s*\(?\s*(?P<ref>(?:[<>≤≥]=?\s*)?{NUMBER}(?:\s*-\s*{NUMBER})?)?\s*\)?$")   # "92 mg/dL (70 - 99)"
DATE_VALUE = re.compile(r"^\d{1,2}\s*[/-]\s*\d{1,2}\s*[/-]\s*\d{2,4}\b|^\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}$")
STATEMENT = re.compile(r"^(?P<key>[A-Za-z][A-Za-z ./()'&]{1,40}?)\s*[-:]\s+(?P<value>\S.{0,40})$")
SINGLE_SPACE_ROW = re.compile(
    rf"^(?P<label>[A-Za-z][A-Za-z0-9 ./()&,'\-]*?[A-Za-z)'.])\s+(?:(?P<flag>HH|LL|H|L)\s+)?(?P<value>\d+\s*:\s*\d+|{NUMBER})\b(?P<tail>.*)$")
CENTERED = 20           # a line indented this far, alone on its line, is a heading
GROUP_MAX_LENGTH = 60


@dataclass
class ResultRow:
    section: str                     # the headings above the row, e.g. "HAEMATOLOGY / COMPLETE BLOOD COUNT (CBC)"
    title: str                       # the test group the row belongs to, e.g. "Semen Examination" (else the nearest heading)
    subgroup: str | None             # a nested label, e.g. "Microscopic Examination"
    label: str                       # test name as printed
    value: str                       # result as printed ("1:20", "Whitish", "155")
    unit: str | None = None
    reference: str | None = None     # printed range / normal text
    flag: str | None = None          # H / L if the laboratory printed one
    text: str = ""                   # the whole row, single-spaced
    number: float | None = None      # the value as a number when it is one

    def as_dict(self) -> dict:
        return {"section": self.section, "title": self.title, "subgroup": self.subgroup, "name": self.label, "value": self.value,
                "unit": self.unit, "reference": self.reference, "printed_flag": self.flag}


@dataclass
class RowReading:
    rows: list[ResultRow] = field(default_factory=list)
    placeholder_sections: dict[str, int] = field(default_factory=dict)       # section -> template fields left unfilled
    text_only_sections: dict[str, str] = field(default_factory=dict)         # section -> first printed line, for sections with text but no result row


def _segments(line: str) -> list[tuple[int, str]]:
    """The cells of a printed row: pieces separated by two or more spaces, with their column."""
    return [(m.start(), m.group().strip()) for m in re.finditer(r"\S(?:(?!\s{2,}).)*", line)]


def _number(text: str) -> float | None:
    m = NUMERIC_VALUE.match(text.strip())
    return float(re.sub(r"[<>\s,]", "", text)) if m else None


_HEADER_WORD = re.compile("|".join(sorted((re.escape(w) for w in TABLE_HEADER_WORDS), key=len, reverse=True)), re.IGNORECASE)


def _is_table_header(plain: str) -> bool:
    """"TEST  VALUE  UNIT  REFERENCE": a line made only of column titles (two or more of them)."""
    found = _HEADER_WORD.findall(plain)
    return len(found) >= 2 and not _HEADER_WORD.sub("", plain).strip(" .,/")


def _is_heading(line: str, cells: list[tuple[int, str]], allow_centered: bool = True) -> bool:
    text = line.strip()
    if re.search(r"\d", text) or len(text) > GROUP_MAX_LENGTH or len(text) < 4 or len(cells) != 1:
        return False
    if re.fullmatch(r"[A-Z][A-Z &/,()\-]+", text):
        return True
    return allow_centered and len(line) - len(line.lstrip()) >= CENTERED


def _looks_like_prose(text: str) -> bool:
    return len(text) > GROUP_MAX_LENGTH or text.endswith(".") or bool(re.match(r"\d", text))


def _split_cells(rest: list[str]) -> tuple[str | None, str | None, str | None, str | None]:
    """cells after the test name -> (flag, value, unit, reference)."""
    flag = value = unit = reference = None
    for cell in rest:
        if flag is None and value is None and FLAG_CELL.match(cell):
            flag = cell.upper()
        elif value is None:
            value = cell
        elif reference is None and REFERENCE_CELL.match(cell):
            reference = cell
        elif unit is None and not REFERENCE_CELL.match(cell):
            unit = cell
        elif reference is None:
            reference = cell
    return flag, value, unit, reference


def read_rows(text: str) -> RowReading:
    """Walk the report line by line, tracking the heading, the table and the group each row sits in."""
    reading = RowReading()
    headings: list[str] = []                 # the run of heading lines just above the current content
    groups: list[tuple[int, str]] = []       # (indent, label) of the group labels in force
    in_table = in_notes = False
    after_heading = False                    # True while the last thing seen was a heading (a new heading then extends the run)

    def section() -> str:
        return " / ".join(headings)

    def title() -> str:
        return groups[0][1] if groups else (headings[-1] if headings else "")

    def add(row: ResultRow) -> None:
        row.section, row.title = section(), title()
        row.subgroup = " / ".join(g[1] for g in groups[1:]) or None
        reading.rows.append(row)

    for raw in text.splitlines():
        if not raw.strip():
            continue
        line = raw.replace("\t", "    ").rstrip()
        cells = _segments(line)
        plain = re.sub(r"\s+", " ", line).strip()
        indent = len(line) - len(line.lstrip())

        if FURNITURE.search(plain):
            if re.search(r"page\s+\d+\s+of\s+\d+|patient(?:'s)?\s+name", plain, re.IGNORECASE):
                in_notes = False                               # a new page starts: the notes of the page before are over
            continue
        if _is_table_header(plain):
            in_table, in_notes, groups = True, False, []
            after_heading = False
            continue
        if _is_heading(line, cells, allow_centered=not in_notes):      # inside a table of notes, an indented word is a table cell, not a heading
            if not after_heading:
                headings = []
            headings.append(plain)
            after_heading, in_table, in_notes, groups = True, False, False, []
            continue
        after_heading = False
        if NOTES_HEADING.match(plain):
            in_notes = True
            continue
        if in_notes:
            continue
        if PLACEHOLDER.search(plain):
            reading.placeholder_sections[section()] = reading.placeholder_sections.get(section(), 0) + 1
            continue

        if len(cells) >= 2 and (in_table or _number(cells[1][1]) is not None or RATIO_VALUE.match(cells[1][1])):
            label, rest = cells[0][1], [c for _, c in cells[1:]]
            flag, value, unit, reference = _split_cells(rest)
            if value is None:
                continue
            while groups and groups[-1][0] >= indent:
                groups.pop()                                   # a row printed further left than a group label ends that group
            add(ResultRow("", "", None, label, value, unit, reference, flag, plain, _number(value)))
            continue

        if len(cells) == 1:
            statement = STATEMENT.match(plain)
            if statement and not _looks_like_prose(plain) and not METADATA_KEYS.match(statement["key"].strip()) and not in_table:
                value, unit, reference = statement["value"].strip(), None, None
                if DATE_VALUE.match(value):
                    continue                                       # "Report Date: 03/07/2026" is a header, not a result
                parts = VALUE_UNIT_RANGE.match(value) or VALUE_WITH_UNIT.match(value)
                if parts:
                    value, unit = parts.group(1) if parts.re is VALUE_WITH_UNIT else parts["num"], parts.group(2) if parts.re is VALUE_WITH_UNIT else parts["unit"]
                    reference = None if parts.re is VALUE_WITH_UNIT else (parts["ref"] or None)
                add(ResultRow("", "", None, statement["key"].strip(), value, unit, reference, None, plain, _number(value)))
                continue
            single = SINGLE_SPACE_ROW.match(plain)
            if single and not in_notes:                          # text whose column spacing was lost: only rows that end in a number can be read
                tail = single["tail"].strip()
                unit_part, reference = (tail, None)
                ref_match = re.search(rf"(?:^|\s)((?:[<>≤≥]=?\s*)?{NUMBER}(?:\s*-\s*{NUMBER})?)\s*$", tail)
                if ref_match:
                    unit_part, reference = tail[: ref_match.start()].strip(), ref_match.group(1).strip()
                add(ResultRow("", "", None, single["label"].strip(), single["value"].strip(), unit_part or None, reference, (single["flag"] or None),
                              plain, _number(single["value"])))
                continue
            if not _looks_like_prose(plain) and not METADATA_KEYS.match(plain):
                while groups and groups[-1][0] >= indent:
                    groups.pop()
                groups.append((indent, plain))                   # a label with no result of its own: "Semen Examination", "Widal Test (Slide Method)"
                continue

        if not _looks_like_prose(plain) or len(plain) <= GROUP_MAX_LENGTH:
            reading.text_only_sections.setdefault(section(), plain)

    # a section that has result rows is not "text only"
    with_rows = {row.section for row in reading.rows}
    reading.text_only_sections = {s: t for s, t in reading.text_only_sections.items() if s not in with_rows}
    return reading
