from typing import Any

from app.schemas.transaction import Transaction, ValidationError
from app.services.configuration import get_config
from app.services.json_number import JsonNumber
from app.services.validator import (
    normalize_amount,
    normalize_identifier,
    normalize_status,
    normalize_timestamp,
    validate_currency,
)


_CANONICAL_FIELD_ORDER = (
    "transaction_id",
    "amount",
    "currency",
    "timestamp",
    "status",
)


def detect_source(payload: dict[str, Any]) -> str | None:
    matches = [
        source
        for source, definition in get_config()["sources"].items()
        if any(detector in payload for detector in definition["detectors"])
    ]
    return matches[0] if len(matches) == 1 else None


def _validate_record(payload: dict[str, Any], source: str) -> Transaction:
    definition = get_config()["sources"][source]
    normalized: dict[str, Any] = {
        "transaction_id": None,
        "amount": None,
        "currency": None,
        "timestamp": None,
        "status": None,
    }
    errors: list[ValidationError] = []

    for canonical_field in _CANONICAL_FIELD_ORDER:
        source_field = definition["fields"][canonical_field]
        if source_field is None:
            continue
        if source_field not in payload:
            errors.append(
                ValidationError(
                    canonical_field,
                    "REQUIRED_MISSING",
                    f"Falta el campo obligatorio '{source_field}'.",
                )
            )
            continue

        value = payload[source_field]
        if canonical_field == "transaction_id":
            result, error = normalize_identifier(value)
        elif canonical_field == "amount":
            result, error = normalize_amount(value)
        elif canonical_field == "currency":
            result, error = validate_currency(value)
        elif canonical_field == "timestamp":
            result, error = normalize_timestamp(value)
        else:
            result, error = normalize_status(value, source)
        normalized[canonical_field] = result
        if error is not None:
            errors.append(error)

    return Transaction(
        **normalized,
        source=source,
        is_valid=not errors,
        errors=errors,
        source_payload=payload,
    )


def normalize_record(payload: Any) -> Transaction:
    if not isinstance(payload, dict):
        return Transaction(
            transaction_id=None,
            source="unknown",
            amount=None,
            currency=None,
            timestamp=None,
            status=None,
            is_valid=False,
            errors=[
                ValidationError(
                    "$",
                    "RECORD_INVALID",
                    "Cada transacción debe ser un objeto JSON.",
                ),
                ValidationError(
                    "source", "SOURCE_UNKNOWN", "No se pudo identificar la fuente."
                ),
            ],
            source_payload=payload,
        )

    source = detect_source(payload)
    if source is None:
        return Transaction(
            transaction_id=None,
            source="unknown",
            amount=None,
            currency=None,
            timestamp=None,
            status=None,
            is_valid=False,
            errors=[
                ValidationError(
                    "source", "SOURCE_UNKNOWN", "No se pudo identificar la fuente."
                )
            ],
            source_payload=payload,
        )
    return _validate_record(payload, source)


def is_duplicate_key(transaction: Transaction) -> tuple[str, str] | None:
    if transaction.source == "unknown" or transaction.transaction_id is None:
        return None
    return transaction.source, transaction.transaction_id
