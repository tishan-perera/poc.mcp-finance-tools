"""Dollar amounts as integer cents, formatted as plain decimal strings."""

from __future__ import annotations

import math
from decimal import Decimal, InvalidOperation

MAX_LINE_CENTS = 1_000_000_000  # $10,000,000.00


def cents_to_decimal(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    amount = abs(int(cents))
    return f"{sign}{amount // 100}.{amount % 100:02d}"


def decimal_to_cents(value: object) -> int:
    """Parse a dollar amount. Rejects commas, extra precision, and non-finite values."""
    if isinstance(value, bool) or value is None:
        raise ValueError("amount must be a dollar value")
    if isinstance(value, Decimal):
        amount = value
    elif isinstance(value, int):
        amount = Decimal(value)
    elif isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("amount must be a finite dollar value")
        amount = Decimal(str(value))
    elif isinstance(value, str):
        text = value.strip().replace("$", "")
        if text == "" or "," in text:
            raise ValueError("amount must be a plain dollar value with at most 2 decimal places")
        try:
            amount = Decimal(text)
        except InvalidOperation as exc:
            raise ValueError("amount must be a plain dollar value") from exc
    else:
        raise ValueError("amount must be a dollar value")
    if not amount.is_finite():
        raise ValueError("amount must be a finite dollar value")
    quantized = amount.quantize(Decimal("0.01"))
    if quantized != amount:
        raise ValueError("use at most 2 decimal places")
    return int(quantized * 100)
