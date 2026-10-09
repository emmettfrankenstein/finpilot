"""Small, strict field parsers used by the CSV validators.

Each parser appends a human-readable reason to `errors` and returns None on failure, so a row
can report every problem at once instead of stopping at the first one.
"""

import re
from datetime import date
from decimal import Decimal, InvalidOperation

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")


class RowErrors(list):
    def add(self, field: str, message: str) -> None:
        self.append(f"{field}: {message}")


def text(
    raw: dict,
    field: str,
    errors: RowErrors,
    *,
    max_length: int,
    required: bool = True,
    pattern: re.Pattern | None = None,
) -> str | None:
    value = (raw.get(field) or "").strip()
    if not value:
        if required:
            errors.add(field, "is required")
        return None
    if len(value) > max_length:
        errors.add(field, f"longer than {max_length} characters")
        return None
    if pattern is not None and not pattern.match(value):
        errors.add(field, f"'{value}' has an invalid format")
        return None
    return value


def enum(raw: dict, field: str, errors: RowErrors, choices) -> str | None:
    value = (raw.get(field) or "").strip()
    if value not in choices.values:
        allowed = "/".join(choices.values)
        errors.add(field, f"'{value}' is not one of {allowed}" if value else "is required")
        return None
    return value


def iso_date(raw: dict, field: str, errors: RowErrors) -> date | None:
    value = (raw.get(field) or "").strip()
    try:
        return date.fromisoformat(value)
    except ValueError:
        errors.add(field, f"'{value}' is not a valid YYYY-MM-DD date" if value else "is required")
        return None


def decimal(
    raw: dict,
    field: str,
    errors: RowErrors,
    *,
    places: int,
    min_value: Decimal | None = None,
    gt: Decimal | None = None,
    max_digits: int = 18,
) -> Decimal | None:
    value = (raw.get(field) or "").strip()
    try:
        number = Decimal(value)
    except InvalidOperation:
        errors.add(field, f"'{value}' is not a number" if value else "is required")
        return None
    if not number.is_finite():
        errors.add(field, "must be a finite number")
        return None
    if min_value is not None and number < min_value:
        errors.add(field, f"{number} must be >= {min_value}")
        return None
    if gt is not None and number <= gt:
        errors.add(field, f"{number} must be > {gt}")
        return None
    if -number.as_tuple().exponent > places:
        errors.add(field, f"{number} has more than {places} decimal places")
        return None
    if len(number.as_tuple().digits) - max(-number.as_tuple().exponent, 0) > max_digits - places:
        errors.add(field, f"{number} is too large")
        return None
    return number


def integer(
    raw: dict, field: str, errors: RowErrors, *, min_value: int, max_value: int
) -> int | None:
    value = (raw.get(field) or "").strip()
    try:
        number = int(value)
    except ValueError:
        errors.add(field, f"'{value}' is not a whole number" if value else "is required")
        return None
    if not min_value <= number <= max_value:
        errors.add(field, f"{number} must be between {min_value} and {max_value}")
        return None
    return number
