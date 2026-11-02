import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from app.schemas.transaction import ValidationError
from app.services.configuration import get_config
from app.services.json_number import JsonNumber


_AMOUNT_PATTERN = re.compile(r"-?\d+(?:\.\d+)?\Z")
_ISO_WITH_TIMEZONE = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
    r"(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})\Z"
)
_ISO_WITHOUT_TIMEZONE = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?\Z"
)
_SPACE_DATETIME = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\Z")
_DATE_ONLY = re.compile(r"\d{4}-\d{2}-\d{2}\Z")


def is_missing(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def normalize_identifier(value: Any) -> tuple[str | None, ValidationError | None]:
    if is_missing(value):
        return None, ValidationError(
            "transaction_id", "REQUIRED_MISSING", "El identificador es obligatorio."
        )
    if isinstance(value, bool) or isinstance(value, (float, Decimal)):
        return None, ValidationError(
            "transaction_id",
            "IDENTIFIER_INVALID",
            "El identificador debe ser texto o un número entero.",
        )
    if not isinstance(value, (str, int)):
        return None, ValidationError(
            "transaction_id",
            "IDENTIFIER_INVALID",
            "El identificador debe ser texto o un número entero.",
        )
    identifier = str(value).strip()
    if not identifier:
        return None, ValidationError(
            "transaction_id", "REQUIRED_MISSING", "El identificador es obligatorio."
        )
    return identifier, None


def normalize_amount(value: Any) -> tuple[Decimal | None, ValidationError | None]:
    if is_missing(value):
        return None, ValidationError(
            "amount", "REQUIRED_MISSING", "El monto es obligatorio."
        )
    if isinstance(value, bool):
        return None, ValidationError(
            "amount", "AMOUNT_INVALID", "El monto debe ser un valor numérico válido."
        )

    if isinstance(value, str):
        text = value
        if not text or not _AMOUNT_PATTERN.fullmatch(text):
            return None, ValidationError(
                "amount",
                "AMOUNT_INVALID",
                "Use dígitos y, opcionalmente, punto decimal; no se permiten comas ni notación científica.",
            )
        try:
            amount = Decimal(text)
        except InvalidOperation:
            return None, ValidationError(
                "amount", "AMOUNT_INVALID", "El monto no es un decimal válido."
            )
    elif isinstance(value, JsonNumber):
        if "e" in value.raw.casefold():
            return None, ValidationError(
                "amount",
                "AMOUNT_INVALID",
                "La notación científica no está permitida.",
            )
        try:
            amount = value.as_decimal()
        except InvalidOperation:
            return None, ValidationError(
                "amount", "AMOUNT_INVALID", "El monto no es un decimal válido."
            )
    elif (
        isinstance(value, Decimal)
        and value.is_finite()
        and value.as_tuple().exponent > 0
    ):
        return None, ValidationError(
            "amount",
            "AMOUNT_INVALID",
            "La notación científica no está permitida.",
        )
    elif isinstance(value, (int, float, Decimal)):
        try:
            amount = Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None, ValidationError(
                "amount", "AMOUNT_INVALID", "El monto no es un decimal válido."
            )
    else:
        return None, ValidationError(
            "amount", "AMOUNT_INVALID", "El monto debe ser numérico."
        )

    if not amount.is_finite():
        return None, ValidationError(
            "amount", "AMOUNT_INVALID", "El monto debe ser finito."
        )
    if amount < 0:
        return None, ValidationError(
            "amount", "AMOUNT_NEGATIVE", "El monto no puede ser negativo."
        )

    maximum_places = get_config()["amount_rules"]["maximum_decimal_places"]
    if max(-amount.as_tuple().exponent, 0) > maximum_places:
        return None, ValidationError(
            "amount",
            "AMOUNT_PRECISION",
            f"El monto admite como máximo {maximum_places} decimales.",
        )
    return amount, None


def validate_currency(value: Any) -> tuple[str | None, ValidationError | None]:
    if is_missing(value):
        return None, ValidationError(
            "currency", "REQUIRED_MISSING", "La moneda es obligatoria."
        )
    if not isinstance(value, str):
        return None, ValidationError(
            "currency", "CURRENCY_INVALID", "La moneda debe ser un código de texto."
        )
    if value not in get_config()["currencies"]:
        return None, ValidationError(
            "currency",
            "CURRENCY_UNSUPPORTED",
            f"La moneda '{value}' no está permitida.",
        )
    return value, None


def normalize_status(
    value: Any, source: str
) -> tuple[str | None, ValidationError | None]:
    if is_missing(value):
        return None, ValidationError(
            "status", "REQUIRED_MISSING", "El estado es obligatorio."
        )
    if not isinstance(value, str):
        return None, ValidationError(
            "status", "STATUS_INVALID", "El estado debe ser texto."
        )
    status_map = get_config()["sources"][source]["status_map"]
    canonical_status = status_map.get(value.strip().casefold())
    if canonical_status is None:
        return None, ValidationError(
            "status", "STATUS_UNKNOWN", f"El estado '{value}' no está mapeado."
        )
    return canonical_status, None


def normalize_timestamp(value: Any) -> tuple[str | None, ValidationError | None]:
    if is_missing(value):
        return None, ValidationError(
            "timestamp", "REQUIRED_MISSING", "La fecha es obligatoria."
        )
    if not isinstance(value, str):
        return None, ValidationError(
            "timestamp", "DATE_INVALID", "La fecha debe ser una cadena de texto."
        )

    allowed_formats = get_config()["datetime_formats"]
    parsers = (
        ("iso8601_datetime_with_timezone", _ISO_WITH_TIMEZONE),
        ("iso8601_datetime_without_timezone", _ISO_WITHOUT_TIMEZONE),
        ("yyyy_mm_dd_hh_mm_ss", _SPACE_DATETIME),
        ("yyyy_mm_dd", _DATE_ONLY),
    )
    matching_format = next(
        (name for name, pattern in parsers if pattern.fullmatch(value)), None
    )
    if matching_format is None or matching_format not in allowed_formats:
        return None, ValidationError(
            "timestamp",
            "DATE_INVALID",
            "La fecha no corresponde a un formato permitido.",
        )

    try:
        if matching_format == "yyyy_mm_dd":
            parsed = datetime.strptime(value, "%Y-%m-%d")
        else:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None, ValidationError(
            "timestamp", "DATE_INVALID", "La fecha no es válida."
        )

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    try:
        normalized = parsed.astimezone(timezone.utc).isoformat(timespec="auto")
    except (OverflowError, ValueError):
        return None, ValidationError(
            "timestamp",
            "DATE_NORMALIZATION_FAILED",
            "La fecha no puede normalizarse a UTC.",
        )
    return normalized.replace("+00:00", "Z"), None
