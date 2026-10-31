"""Turns Pydantic's technical error list into plain sentences, one per field, for the 422 answer.

The answer looks like {"detail": "Full name: The name can contain only letters ...", "errors": [{"field": "full_name", "message": "..."}]}.
`detail` is one readable sentence (every client can show it as it is); `errors` lets a form put each message under its own field."""
import re


def _label(loc) -> tuple[str, str]:
    """('full_name', 'Full name') from the location of the error, ignoring 'body', 'query', 'path' and list positions."""
    parts = [str(p) for p in loc if str(p) not in ("body", "query", "path", "header", "cookie") and not str(p).isdigit()]
    field = parts[-1] if parts else ""
    pretty = re.sub(r"\s+", " ", field.replace("_", " ")).strip().capitalize()
    return field, pretty


def message_of(err: dict) -> str:
    """One plain sentence for one error."""
    kind = err.get("type", "")
    ctx = err.get("ctx") or {}
    msg = str(err.get("msg", "This value is not valid."))
    if kind == "missing":
        return "This is required."
    if kind == "string_too_short":
        return f"Please enter at least {ctx.get('min_length')} characters." if ctx.get("min_length", 0) > 1 else "This is required."
    if kind == "string_too_long":
        return f"Please keep this under {ctx.get('max_length')} characters."
    if kind in ("too_short", "too_long"):
        return "Please add at least one item." if kind == "too_short" else f"Please give no more than {ctx.get('max_length')} items."
    if kind in ("greater_than", "greater_than_equal"):
        return f"The value must be {'more than' if kind == 'greater_than' else 'at least'} {ctx.get('gt', ctx.get('ge'))}."
    if kind in ("less_than", "less_than_equal"):
        return f"The value must be {'less than' if kind == 'less_than' else 'at most'} {ctx.get('lt', ctx.get('le'))}."
    if kind in ("int_parsing", "int_from_float", "int_type"):
        return "Please enter a whole number."
    if kind in ("float_parsing", "float_type", "finite_number"):
        return "Please enter a number."
    if kind in ("bool_parsing", "bool_type"):
        return "Please choose yes or no."
    if kind.startswith(("date_", "datetime_", "time_")) or kind in ("date_type", "datetime_type"):
        return "Please enter a valid date."
    if kind in ("literal_error", "enum"):
        expected = ctx.get("expected")
        return f"Please choose one of: {expected.replace(chr(39), '')}." if expected else "Please choose one of the allowed values."
    if kind in ("string_type", "model_type", "dict_type", "list_type"):
        return "This value is not in the right form."
    if kind in ("json_invalid", "model_attributes_type"):
        return "The request could not be read."
    if "valid email address" in msg:
        return "Please enter a valid e-mail address, for example name@example.com."
    if kind == "value_error":
        return re.sub(r"^Value error, ", "", msg)
    if kind == "string_pattern_mismatch":
        return "This value is not in the right form."
    return re.sub(r"^Value error, ", "", msg)


def friendly(errors: list[dict]) -> dict:
    rows, seen = [], set()
    for err in errors:
        field, pretty = _label(err.get("loc", ()))
        message = message_of(err)
        key = (field, message)
        if key in seen:
            continue
        seen.add(key)
        rows.append({"field": field, "label": pretty, "message": message})
    sentence = " ".join(f"{r['label']}: {r['message']}" if r["label"] else r["message"] for r in rows[:4])
    if len(rows) > 4:
        sentence += f" (and {len(rows) - 4} more)"
    return {"detail": sentence or "Some of the information is not valid.", "errors": rows}
