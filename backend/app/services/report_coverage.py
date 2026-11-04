"""Coverage check: how much of the printed report did the analysis really cover?

Every printed result row (report_rows.py) ends in exactly one of four places:
  analysed   - read by the deterministic engine and compared with its printed range (or marked "No normal range");
  printed    - a row of a section that is not a blood panel (Widal, semen examination, Mantoux ...): shown "as printed", never judged;
  unread     - a row of a blood-panel section that the engine could not turn into a result: listed in a warning;
  ignored    - a section holding only an unfilled template ("<IMPRESSION>"): listed, so that nobody thinks it was analysed.
The numbers and the message are built here once, and every screen (dashboard, analysis table, short summary, printed PDF) shows the same ones.
The report is never described as fully analysed unless every row ended in "analysed"."""
import re
from dataclasses import dataclass

from app.services.normalization_service import match_parameter_name
from app.services.report_rows import ResultRow, RowReading, read_rows

# Headings of sections whose tests are blood-chemistry style panels that the engine is built for. Everything else (serology titres, semen,
# skin tests, cytology ...) is shown as printed. A heading nobody recognises counts as "other", never as analysed.
BLOOD_PANEL_HEADING = re.compile(
    r"haemat|hemat|biochem|blood|lipid|liver|kidney|renal|thyroid|endocrin|diabet|glyc|vitamin|electrolyte|iron|profile|function\s+test|cbc|lft|kft|tft|"
    r"serum|plasma|coagul|cardiac|hormon|urine|urinalysis|chemistry", re.IGNORECASE)
VALUE_TOLERANCE = 1e-6


@dataclass
class Coverage:
    detected_rows: int
    analysed_rows: int
    printed_only_rows: int
    unread_rows: list[dict]
    skipped_sections: list[dict]
    printed_only_sections: list[str]
    unverified_results: int = 0          # results the engine read that no printed row could be matched to (a layout the row reader cannot follow)

    @property
    def complete(self) -> bool:
        return not (self.printed_only_rows or self.unread_rows or self.skipped_sections or self.unverified_results)

    @property
    def headline(self) -> str:
        if self.complete:
            return ""
        known_gap = self.printed_only_rows or self.unread_rows or self.skipped_sections
        return "Not the whole report was analysed" if known_gap else "The coverage of this report could only be partly checked"

    def message(self) -> str:
        if self.detected_rows == 0 and not self.skipped_sections:
            return "No printed result rows were detected, so nothing can be said about how much of the report was analysed."
        parts = [f"{self.analysed_rows} of {self.detected_rows} printed result rows were analysed against the printed range."]
        if self.printed_only_rows:
            parts.append(f"{self.printed_only_rows} row{'s' if self.printed_only_rows != 1 else ''} ({', '.join(self.printed_only_sections)}) "
                         f"{'are' if self.printed_only_rows != 1 else 'is'} shown as printed under Other results and {'were' if self.printed_only_rows != 1 else 'was'} not judged.")
        if self.unread_rows:
            parts.append(f"{len(self.unread_rows)} row{'s' if len(self.unread_rows) != 1 else ''} could not be read and {'were' if len(self.unread_rows) != 1 else 'was'} not analysed: "
                         + "; ".join(r["text"] for r in self.unread_rows[:5]) + (f" and {len(self.unread_rows) - 5} more" if len(self.unread_rows) > 5 else "") + ".")
        for s in self.skipped_sections:
            parts.append(f"Section \"{s['section']}\" was not analysed: {s['reason']}")
        if self.unverified_results:
            parts.append(f"{self.unverified_results} result{'s were' if self.unverified_results != 1 else ' was'} read from a layout the row check could not follow, "
                         "so it cannot be confirmed that every printed row was analysed.")
        if self.complete:
            parts = [f"All {self.detected_rows} printed result rows were analysed against the printed range."]
        return " ".join(parts)

    def as_dict(self) -> dict:
        return {"detected_rows": self.detected_rows, "analysed_rows": self.analysed_rows, "printed_only_rows": self.printed_only_rows,
                "unread_rows": self.unread_rows, "skipped_sections": self.skipped_sections, "printed_only_sections": self.printed_only_sections,
                "unverified_results": self.unverified_results, "complete": self.complete, "headline": self.headline, "message": self.message()}


def _is_blood_panel(section: str) -> bool:
    return not section or bool(BLOOD_PANEL_HEADING.search(section))      # a report with no headings at all is read as one blood panel


def _matching_result(row: ResultRow, parameters: list) -> int | None:
    """The index of the engine's result for this printed row (same test name and the same printed value), or None."""
    if row.number is None:
        return None
    for context in ("blood", "urine"):                     # a urine row ("Protein", "Pus cells") is only known inside a urine section
        hit = match_parameter_name(row.label, context)
        if hit:
            for index, p in enumerate(parameters):
                if p.extracted.normalized_name == hit.info.name and abs(p.extracted.value - row.number) <= VALUE_TOLERANCE * max(1.0, abs(row.number)):
                    return index
    return None


def _sections_text(sections: list[str]) -> list[str]:
    shown = []
    for s in sections:
        last = s.split(" / ")[-1]
        if last not in shown:
            shown.append(last)
    return shown


def check_coverage(reading: RowReading, parameters: list) -> tuple[Coverage, list[dict]]:
    """-> (the coverage numbers, the rows of non-blood sections to show as 'Other results')."""
    other_results: list[dict] = []
    unread: list[dict] = []
    analysed = 0
    matched: set[int] = set()
    printed_sections: list[str] = []
    for row in reading.rows:
        index = _matching_result(row, parameters)
        if index is not None:
            analysed += 1
            matched.add(index)
        elif _is_blood_panel(row.section):
            unread.append({"section": row.section, "text": row.text})
        else:
            other_results.append(row.as_dict())
            printed_sections.append(row.title or row.section)
    skipped = [{"section": s, "reason": f"it holds only unfilled template text ({n} empty field{'s' if n != 1 else ''}), so there is no result to analyse."}
               for s, n in reading.placeholder_sections.items() if s not in {r.section for r in reading.rows}]
    skipped += [{"section": s, "reason": f"it is text without result rows (\"{t[:60]}\"), so it was not analysed."}
                for s, t in reading.text_only_sections.items() if s not in reading.placeholder_sections]
    coverage = Coverage(detected_rows=len(reading.rows), analysed_rows=analysed, printed_only_rows=len(other_results), unread_rows=unread,
                        skipped_sections=skipped, printed_only_sections=_sections_text(printed_sections),
                        unverified_results=len(parameters) - len(matched))
    return coverage, other_results


def analyse_coverage(text: str, parameters: list) -> tuple[dict, list[dict]]:
    """The whole check on report text that still has its column spacing. Never raises: if the rows cannot be read, the coverage says so."""
    try:
        coverage, other = check_coverage(read_rows(text), parameters)
        return coverage.as_dict(), other
    except Exception:  # noqa: BLE001 - a helper view must never take the analysis down; the report then claims nothing
        return {"detected_rows": 0, "analysed_rows": len(parameters), "printed_only_rows": 0, "unread_rows": [], "skipped_sections": [],
                "printed_only_sections": [], "unverified_results": len(parameters), "complete": False, "headline": "The coverage of this report could only be partly checked",
                "message": "The coverage check could not run on this file, so it is not known whether every printed row was analysed."}, []
