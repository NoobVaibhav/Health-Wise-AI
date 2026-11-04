"""One place for the input rules of the whole application (see docs/VALIDATION_RULES.md).

Every request schema uses these types instead of repeating a rule, so a name, a phone number, a date of birth or a vital sign means the same
thing everywhere. A rule that is broken raises a ValueError with a plain-English message; FastAPI answers 422 with that message. Text is
trimmed, HTML tags and control characters are removed, and nothing here ever raises anything but ValueError."""
import math
import re
from decimal import ROUND_HALF_UP, Decimal
import unicodedata
from datetime import date, datetime, timedelta
from typing import Annotated, Literal

from fastapi import Path, Query
from pydantic import AfterValidator, BeforeValidator, EmailStr, Field, PositiveInt

# ------------------------------------------------------------------ text
TAG_RE = re.compile(r"<[^>]*>?")                       # a tag, also one that is not closed
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f​-‏‪-‮⁦-⁩]")   # control, zero-width and direction-override characters


def clean_text(value, *, multiline: bool = False):
    """Trim, remove HTML tags and control characters. Newlines and tabs are kept only for multi-line text."""
    if value is None or not isinstance(value, str):
        return value
    value = TAG_RE.sub("", value.replace("\r\n", "\n").replace("\r", "\n"))
    value = CONTROL_RE.sub("", value)
    if multiline:
        return "\n".join(line.rstrip() for line in value.strip().split("\n"))
    return re.sub(r"[ \t\n]+", " ", value).strip()


def _single_line(value):
    return clean_text(value)


def _multi_line(value):
    return clean_text(value, multiline=True)


def text(max_length: int, *, min_length: int = 0, multiline: bool = False):
    """An optional-or-required free text type: cleaned first, then length-checked (a text of only spaces counts as empty)."""
    def check(value):
        if value is None:
            return value
        if min_length and len(value) < min_length:
            raise ValueError("This is required." if min_length <= 1 and not value else f"Please enter at least {min_length} characters.")
        if len(value) > max_length:
            raise ValueError(f"Please keep this under {max_length} characters (it has {len(value)}).")
        return value
    return Annotated[str, BeforeValidator(_multi_line if multiline else _single_line), AfterValidator(check)]


def empty_to_none(value):
    """An empty or space-only text from a form means "not given"."""
    cleaned = clean_text(value) if isinstance(value, str) else value
    return None if cleaned == "" else value


# ------------------------------------------------------------------ e-mail, names, phone, address
def _email_pre(value):
    return value.strip().lower() if isinstance(value, str) else value


def _email_post(value: str) -> str:
    if len(value) > 254:
        raise ValueError("The e-mail address is too long (254 characters at most).")
    if re.search(r"\s", value):
        raise ValueError("The e-mail address cannot contain spaces.")
    return value


Email = Annotated[EmailStr, BeforeValidator(_email_pre), AfterValidator(_email_post)]

NAME_EXTRA = set(" '.-’")


def _name(value: str) -> str:
    value = clean_text(value) if isinstance(value, str) else value
    if not isinstance(value, str) or len(value) < 2:
        raise ValueError("Please enter the full name (at least 2 characters).")
    if len(value) > 150:
        raise ValueError("The name is too long (150 characters at most).")
    for ch in value:
        if not (ch.isalpha() or unicodedata.category(ch).startswith("M") or ch in NAME_EXTRA):
            raise ValueError("The name can contain only letters, spaces, apostrophes, hyphens and dots.")
    if not any(ch.isalpha() for ch in value):
        raise ValueError("The name must contain letters.")
    return value


def _name_pre(value):
    """A name with markup or control characters is refused (not cleaned into a different name); extra spaces are collapsed."""
    if isinstance(value, str):
        if re.search(r"[<>]", value) or CONTROL_RE.search(value):
            raise ValueError("The name can contain only letters, spaces, apostrophes, hyphens and dots.")
        return re.sub(r"\s+", " ", value).strip()
    return value


PersonName = Annotated[str, BeforeValidator(_name_pre), AfterValidator(_name)]


OptionalPersonName = Annotated[str | None, BeforeValidator(empty_to_none), BeforeValidator(_name_pre), AfterValidator(lambda v: v if v is None else _name(v))]


def normalise_phone(value: str) -> str:
    """'+91 98765 43210', '098765-43210', '(98765) 43210' -> '9876543210' (Indian mobile) or '+<country code and number>'."""
    raw = clean_text(value)
    plus = raw.startswith("+")
    digits = re.sub(r"[\s\-().]", "", raw[1:] if plus else raw)
    if not digits.isdigit():
        raise ValueError("The phone number can contain only digits, spaces, dashes, brackets and a leading +.")
    if plus:
        if digits.startswith("91") and len(digits) == 12 and digits[2] in "6789":
            return digits[2:]
        if not 8 <= len(digits) <= 15:
            raise ValueError("A phone number with a + needs the country code and 8 to 15 digits in all.")
        return "+" + digits
    if len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    if not re.fullmatch(r"[6-9]\d{9}", digits):
        raise ValueError("Please enter a 10-digit mobile number starting with 6, 7, 8 or 9 (or a number with a + and country code).")
    return digits


def _phone(value):
    return None if value is None else normalise_phone(value)


Phone = Annotated[str, BeforeValidator(_single_line), AfterValidator(_phone)]
OptionalPhone = Annotated[str | None, BeforeValidator(empty_to_none), BeforeValidator(_single_line), AfterValidator(_phone)]

def _address(value):
    if value is not None and len(value) > 300:
        raise ValueError("The address is too long (300 characters at most).")
    return value


Address = Annotated[str | None, BeforeValidator(empty_to_none), BeforeValidator(_single_line), AfterValidator(_address)]


def _pincode(value):
    if value is None:
        return value
    if not re.fullmatch(r"\d{6}", value):
        raise ValueError("The pincode must be 6 digits.")
    return value


Pincode = Annotated[str | None, BeforeValidator(empty_to_none), AfterValidator(_pincode)]

GENDERS = ("male", "female", "other")


def _gender(value):
    if value is None:
        return value
    v = str(value).strip().lower()
    if v == "":
        return None
    if v not in GENDERS:
        raise ValueError("The gender must be male, female or other.")
    return v


Gender = Annotated[str | None, BeforeValidator(_gender)]

BLOOD_GROUPS = ("A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-")


def _blood_group(value):
    if value is None:
        return value
    v = str(value).strip().upper().replace(" ", "")
    if v == "":
        return None
    if v not in BLOOD_GROUPS:
        raise ValueError("The blood group must be one of A+, A-, B+, B-, AB+, AB-, O+, O-.")
    return v


BloodGroup = Annotated[str | None, BeforeValidator(_blood_group)]


# ------------------------------------------------------------------ dates
MIN_DATE = date(1930, 1, 1)           # the earliest date of birth accepted


def _date_of_birth(value):
    if value is None:
        return value
    today = date.today()
    if value > today:
        raise ValueError("The date of birth cannot be in the future.")
    if value < MIN_DATE:
        raise ValueError("The date of birth cannot be before 1930.")
    age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
    if age > 120:
        raise ValueError("The age cannot be more than 120 years.")
    return value


DateOfBirth = Annotated[date | None, AfterValidator(_date_of_birth)]


def age_warning(dob: date | None) -> str | None:
    """A warning (never an error) for an age that is possible but unusual."""
    if dob is None:
        return None
    today = date.today()
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    if age < 1:
        return "This patient is under 1 year old. Please check the date of birth."
    if age > 110:
        return f"This patient would be {age} years old. Please check the date of birth."
    return None


def _not_future(value):
    if value is not None and value > date.today():
        raise ValueError("This date cannot be in the future.")
    return value


def _planned_date(value):
    """A date a doctor sets ahead (follow-up, due date, expected discharge): a real recent-century date, at most 2 years ahead."""
    if value is None:
        return value
    if value < date(1900, 1, 1):
        raise ValueError("Please enter a valid date.")
    if value > date.today() + timedelta(days=731):
        raise ValueError("This date is too far ahead. Please choose a date within 2 years.")
    return value


def _not_far_future(value):
    """A time recorded after the fact (a timeline entry): not in the future (one hour of grace for clock differences)."""
    if value is not None and value > datetime.now() + timedelta(hours=1):
        raise ValueError("This time cannot be in the future.")
    return value


PlannedDate = Annotated[date | None, AfterValidator(_planned_date)]
RecordedTime = Annotated[datetime, AfterValidator(_not_far_future)]
PastOrTodayDate = Annotated[date | None, AfterValidator(_not_future)]
PastOrTodayRequired = Annotated[date, AfterValidator(_not_future)]


def check_appointment_time(value: datetime) -> datetime:
    """Not in the past (a 5 minute grace) and not more than 1 year ahead."""
    now = datetime.now()
    if value < now - timedelta(minutes=5):
        raise ValueError("The appointment time must be in the future.")
    if value > now + timedelta(days=366):
        raise ValueError("Appointments can be booked up to 1 year ahead.")
    return value


# ------------------------------------------------------------------ passwords
COMMON_PASSWORDS = {
    "password", "password1", "password12", "password123", "password1234", "passw0rd", "p@ssw0rd", "p@ssword1", "12345678", "123456789", "1234567890", "12345678a", "a1234567",
    "qwerty123", "qwerty1234", "qwertyuiop", "1q2w3e4r", "1qaz2wsx", "admin123", "admin1234", "administrator1", "welcome1", "welcome123", "welcome@123", "letmein123", "iloveyou1",
    "iloveyou123", "abc12345", "abcd1234", "abcd12345", "monkey123", "dragon123", "football1", "baseball1", "sunshine1", "princess1", "master123", "login1234", "changeme1",
    "changeme123", "india123", "india@123", "hospital1", "hospital123", "health123", "doctor123", "patient123", "pharmacy123", "test1234", "test12345", "user1234", "demo12345",
}


def check_password(value: str) -> str:
    """8-128 characters, at least one letter and one number, not a well-known password."""
    if not isinstance(value, str) or len(value) < 8:
        raise ValueError("The password must have at least 8 characters.")
    if len(value) > 128:
        raise ValueError("The password is too long (128 characters at most).")
    if not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
        raise ValueError("The password must contain at least one letter and one number.")
    if value.lower() in COMMON_PASSWORDS or value.lower().rstrip("!@#$%^&*") in COMMON_PASSWORDS:
        raise ValueError("This password is too common. Please choose another one.")
    return value


def password_has_email_name(password: str, email: str | None) -> bool:
    """True if the password contains the name part of the e-mail address (rahul.patil@x.com -> 'rahul.patil', 'rahul', 'patil' of 4+ letters)."""
    if not email or "@" not in email:
        return False
    local = email.split("@")[0].lower()
    pieces = {local} | {p for p in re.split(r"[^a-z]+", local) if len(p) >= 4}
    return any(len(p) >= 4 and p in password.lower() for p in pieces)


NO_NAME_IN_PASSWORD = "The password must not contain your e-mail name."

Password = Annotated[str, AfterValidator(check_password)]


# ------------------------------------------------------------------ vitals and clinical numbers (one table, used by every schema that takes them)
def vital(low: float, high: float, *, integer: bool = False):
    kind = int if integer else float
    return Annotated[kind | None, Field(default=None, ge=low, le=high, allow_inf_nan=False)]


HEIGHT_CM = vital(30, 260)
WEIGHT_KG = vital(1, 500)
PULSE = vital(20, 250, integer=True)
SYSTOLIC = vital(50, 300, integer=True)
DIASTOLIC = vital(30, 200, integer=True)
SPO2 = vital(50, 100, integer=True)
TEMPERATURE_C = vital(30, 45)
TEMPERATURE_F = vital(86, 113)
RESP_RATE = vital(4, 80, integer=True)

LAB_UNITS = {"mg/dl", "g/dl", "mmol/l", "mmol/mol", "meq/l", "iu/l", "u/l", "ng/ml", "pg/ml", "ug/dl", "mcg/dl", "ug/l", "mcg/l", "miu/l", "uiu/ml", "iu/ml", "%", "fl", "pg", "g/l",
             "/cmm", "/ul", "/mm3", "cells/ul", "million/cmm", "million/ul", "lakh/cmm", "10^3/ul", "10^6/ul", "x10^9/l", "x10^12/l", "mm/hr", "mm/h", "sec", "s", "ratio", "ml/min", "ml/min/1.73m2",
             "mg/l", "ng/dl", "umol/l", "nmol/l", "mg/24h", "cm", "mm", "kg", "bpm", "mmhg", "ml", "l", "mg", "g", "ug", "mcg", "iu", "u", "cells/hpf", "/hpf", "/lpf", "index", ""}
MAX_LAB_VALUE = 1_000_000_000


def check_lab_value(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("A lab value must be a number.")
    if value < 0:
        raise ValueError("A lab value cannot be negative.")
    if value > MAX_LAB_VALUE:
        raise ValueError("This lab value is too large to be real. Please check it.")
    return float(value)


def check_lab_unit(unit: str | None) -> str | None:
    if unit is None:
        return unit
    if clean_text(unit).lower().replace(" ", "") not in LAB_UNITS:
        raise ValueError("This unit is not one of the known laboratory units.")
    return unit


# ------------------------------------------------------------------ money, quantities, barcode, prescription
def round_money(value):
    """Rupees and paise: rounded to 2 decimals the way a bill is (half up), not the way a float happens to print."""
    if value is None:
        return None
    return float(Decimal(str(float(value))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


Money = Annotated[float, Field(ge=0, le=10_000_000, allow_inf_nan=False), AfterValidator(round_money)]
OptionalMoney = Annotated[float | None, Field(default=None, ge=0, le=10_000_000, allow_inf_nan=False), AfterValidator(round_money)]
Percent = Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)]
OptionalPercent = Annotated[float | None, Field(default=None, ge=0, le=100, allow_inf_nan=False)]
Quantity = Annotated[int, Field(gt=0, le=1_000_000)]


def _barcode(value):
    if value is None:
        return value
    value = str(value).strip()
    if value == "":
        return None
    if not 4 <= len(value) <= 64 or not re.fullmatch(r"[A-Za-z0-9-]+", value):
        raise ValueError("The barcode must have 4 to 64 letters, digits or hyphens.")
    return value


Barcode = Annotated[str | None, AfterValidator(_barcode)]

DURATION_DAYS_RE = re.compile(r"^\s*(\d{1,3})\s*(?:days?|d)?\s*$", re.IGNORECASE)
DURATION_UNITS = {"day": 1, "days": 1, "d": 1, "week": 7, "weeks": 7, "w": 7, "month": 30, "months": 30, "m": 30}


def check_duration(value: str) -> str:
    """A prescription duration as '5', '5 days', '2 weeks', '1 month': between 1 and 365 days. Text such as 'as needed' or 'ongoing' is allowed."""
    v = clean_text(value)
    if v == "":
        raise ValueError("Please give the duration of the medicine.")
    if re.match(r"^[-−]\s*\d", v):
        raise ValueError("The duration must be more than zero.")
    m = re.fullmatch(r"(\d{1,4})\s*([A-Za-z]*)", v)
    if m and (m.group(2).lower() in DURATION_UNITS or m.group(2) == ""):
        days = int(m.group(1)) * DURATION_UNITS.get(m.group(2).lower(), 1)
        if not 1 <= days <= 365:
            raise ValueError("The duration must be between 1 and 365 days.")
    return v


def check_blood_pressure(systolic, diastolic):
    """The upper reading is higher than the lower one (the other way round is a typing mistake)."""
    if systolic is not None and diastolic is not None and diastolic >= systolic:
        raise ValueError("The upper blood pressure must be higher than the lower one.")


# ------------------------------------------------------------------ ids and query parameters
PositiveId = Annotated[int, Field(gt=0, lt=2_000_000_000)]
PathId = Annotated[int, Path(gt=0, lt=2_000_000_000)]                    # an id in the URL: a positive whole number, else 422
QueryId = Annotated[int | None, Query(gt=0, lt=2_000_000_000)]          # an optional id in the query string


def _search(value):
    if value is None:
        return None
    cleaned = clean_text(value)
    return cleaned or None


SearchText = Annotated[str | None, Query(max_length=100), AfterValidator(_search)]
Limit = Annotated[int, Query(ge=1, le=200)]
Offset = Annotated[int, Query(ge=0, le=10_000_000)]


def one_of(*allowed: str, name: str = "value"):
    """A query parameter that must be one of the allowed words (case-insensitive); anything else is a 422, not a 500."""
    allowed_set = {a.upper() for a in allowed}

    def check(value):
        if value is None or str(value).strip() == "":
            return None
        v = clean_text(value).upper()               # a value that was only markup cleans to "" and is then refused below, not ignored
        if v not in allowed_set:
            raise ValueError(f"The {name} must be one of: {', '.join(sorted(allowed_set))}.")
        return v
    return Annotated[str | None, Query(max_length=40), AfterValidator(check)]


def opt_text(max_length: int, *, multiline: bool = False, min_length: int = 0):
    """Optional free text: cleaned, an empty or space-only value becomes None, and the length is checked."""
    def check(value):
        if value is None:
            return value
        if min_length and len(value) < min_length:
            raise ValueError(f"Please enter at least {min_length} characters.")
        if len(value) > max_length:
            raise ValueError(f"Please keep this under {max_length} characters (it has {len(value)}).")
        return value
    clean = _multi_line if multiline else _single_line
    return Annotated[str | None, BeforeValidator(empty_to_none), BeforeValidator(clean), AfterValidator(check)]
