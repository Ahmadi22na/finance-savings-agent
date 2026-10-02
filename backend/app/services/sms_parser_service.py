"""Module documentation."""
import re
from dataclasses import dataclass


@dataclass
class ParsedSms:
    amount: float
    type: str  # "income" | "expense"
    note: str




_CLIQ_RECEIVED_PATTERN = re.compile(
    r"successfully\s+received\s+(?:jod\s*)?(?P<amount>[\d,]+\.?\d*)\s*(?:jod\s*)?from\s+(?P<sender>\S+)",
    re.IGNORECASE,
)
_CLIQ_TRANSFER_PATTERN = re.compile(
    r"successful\s+transfer\s+of\s+(?:jod\s*)?(?P<amount>[\d,]+\.?\d*)\s*(?:jod\s*)?to\s+(?P<recipient>\S+)",
    re.IGNORECASE,
)


def parse_sms(text: str) -> ParsedSms | None:
    """Parse sms documentation."""
    cleaned = text.strip()
    if not cleaned:
        return None

    match = _CLIQ_RECEIVED_PATTERN.search(cleaned)
    if match:
        return ParsedSms(
            amount=_to_float(match.group("amount")),
            type="income",
            note=f"تحويل CliQ من {match.group('sender')}",
        )

    match = _CLIQ_TRANSFER_PATTERN.search(cleaned)
    if match:
        return ParsedSms(
            amount=_to_float(match.group("amount")),
            type="expense",
            note=f"تحويل CliQ إلى {match.group('recipient')}",
        )

    return None


def _to_float(raw_amount: str) -> float:
    return float(raw_amount.replace(",", ""))
