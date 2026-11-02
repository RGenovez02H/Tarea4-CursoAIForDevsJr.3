from decimal import Decimal

import pytest

from app.services.json_number import JsonNumber
from app.services.normalizer import normalize_record
from app.services.validator import (
    normalize_amount,
    normalize_identifier,
    normalize_timestamp,
    validate_currency,
)


@pytest.mark.parametrize(
    ("payload", "source", "expected_status", "expected_timestamp"),
    [
        (
            {
                "id": " TX-1 ",
                "amount": JsonNumber("100.50"),
                "currency": "USD",
                "timestamp": "2026-10-29T14:30:00-06:00",
                "status": " Success ",
            },
            "format_1",
            "SUCCESS",
            "2026-10-29T20:30:00Z",
        ),
        (
            {
                "transaction_id": 25,
                "total": 0,
                "currency_code": "EUR",
                "created_at": "2026-10-29 14:30:00",
                "state": "COMPLETED",
            },
            "format_2",
            "SUCCESS",
            "2026-10-29T14:30:00Z",
        ),
        (
            {
                "ref": "R-3",
                "amount": JsonNumber("1.25"),
                "date": "2026-10-29",
                "result": "waiting",
            },
            "format_3",
            "PENDING",
            "2026-10-29T00:00:00Z",
        ),
    ],
)
def test_normalizes_source_fields(payload, source, expected_status, expected_timestamp):
    transaction = normalize_record(payload)

    assert transaction.source == source
    assert transaction.status == expected_status
    assert transaction.timestamp == expected_timestamp
    source_identifier = payload.get(
        "id", payload.get("transaction_id", payload.get("ref"))
    )
    assert transaction.transaction_id == str(source_identifier).strip()
    if source == "format_3":
        assert transaction.is_valid is False
        assert any(error.field == "currency" for error in transaction.errors)
    else:
        assert transaction.is_valid is True


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (100, Decimal("100")),
        (JsonNumber("100.50"), Decimal("100.50")),
        ("100.50", Decimal("100.50")),
        ("0", Decimal("0")),
    ],
)
def test_accepts_approved_amounts(value, expected):
    amount, error = normalize_amount(value)

    assert amount == expected
    assert error is None


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "   ",
        "1,000.50",
        "1.000,50",
        "1e2",
        "1E2",
        JsonNumber("1e2"),
        JsonNumber("1E2"),
        JsonNumber("1.5e2"),
        Decimal("1.234"),
        Decimal("1E+2"),
        Decimal("-1"),
        Decimal("Infinity"),
        True,
    ],
)
def test_rejects_invalid_amounts(value):
    amount, error = normalize_amount(value)

    assert amount is None
    assert error is not None


def test_currency_must_match_configured_code_exactly():
    assert validate_currency("GTQ") == ("GTQ", None)
    normalized, error = validate_currency("usd")
    assert normalized is None
    assert error is not None
    assert error.code == "CURRENCY_UNSUPPORTED"


@pytest.mark.parametrize(
    ("source", "field", "input_value", "expected"),
    [
        ("format_1", "status", "pending", "PENDING"),
        ("format_1", "status", "SUCCESS", "SUCCESS"),
        ("format_1", "status", "failed", "FAILED"),
        ("format_1", "status", "CANCELLED", "CANCELLED"),
        ("format_2", "state", "PENDING", "PENDING"),
        ("format_2", "state", "completed", "SUCCESS"),
        ("format_2", "state", "ERROR", "FAILED"),
        ("format_2", "state", "void", "CANCELLED"),
        ("format_3", "result", "waiting", "PENDING"),
        ("format_3", "result", "APPROVED", "SUCCESS"),
        ("format_3", "result", "rejected", "FAILED"),
        ("format_3", "result", "CANCELLED", "CANCELLED"),
    ],
)
def test_status_mappings_are_explicit_and_case_insensitive(
    source, field, input_value, expected
):
    from app.services.validator import normalize_status

    assert normalize_status(f" {input_value} ", source) == (expected, None)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-10-29T14:30:00Z", "2026-10-29T14:30:00Z"),
        ("2026-10-29T14:30:00+00:00", "2026-10-29T14:30:00Z"),
        ("2026-10-29T14:30:00-06:00", "2026-10-29T20:30:00Z"),
        ("2026-10-29T14:30:00", "2026-10-29T14:30:00Z"),
        ("2026-10-29 14:30:00", "2026-10-29T14:30:00Z"),
        ("2026-10-29", "2026-10-29T00:00:00Z"),
    ],
)
def test_normalizes_approved_dates_to_utc(value, expected):
    timestamp, error = normalize_timestamp(value)

    assert timestamp == expected
    assert error is None


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "2026/10/29",
        "10/29/2026",
        "2026-10-29T14:30",
        "2026-10-29T14:30:00.1234567Z",
        "2026-02-30",
    ],
)
def test_rejects_unapproved_or_invalid_dates(value):
    timestamp, error = normalize_timestamp(value)

    assert timestamp is None
    assert error is not None
    assert error.code in {"REQUIRED_MISSING", "DATE_INVALID"}


def test_timestamp_utc_overflow_returns_specific_validation_error():
    timestamp, error = normalize_timestamp("0001-01-01T00:00:00+23:00")

    assert timestamp is None
    assert error is not None
    assert error.code == "DATE_NORMALIZATION_FAILED"
    assert "no puede normalizarse" in error.message


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        " ",
        True,
        False,
        1.5,
        Decimal("1.5"),
        {},
        [],
    ],
)
def test_identifier_values_outside_approved_rules_are_rejected(value):
    identifier, error = normalize_identifier(value)

    assert identifier is None
    assert error is not None
    assert error.code in {"REQUIRED_MISSING", "IDENTIFIER_INVALID"}


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (" TX-1 ", "TX-1"),
        (123, "123"),
        (0, "0"),
    ],
)
def test_identifier_text_and_integers_are_trimmed_or_converted(value, expected):
    identifier, error = normalize_identifier(value)

    assert identifier == expected
    assert error is None


def test_unknown_source_is_retained_as_invalid():
    payload = {"amount": JsonNumber("4.25"), "note": "unrecognized"}

    transaction = normalize_record(payload)

    assert transaction.source == "unknown"
    assert transaction.is_valid is False
    assert transaction.source_payload is payload
    assert [error.code for error in transaction.errors] == ["SOURCE_UNKNOWN"]


def test_invalid_record_collects_all_field_errors():
    transaction = normalize_record(
        {
            "id": "A-1",
            "amount": JsonNumber("1.234"),
            "currency": "CAD",
            "timestamp": "not-a-date",
            "status": "unknown",
        }
    )

    assert transaction.is_valid is False
    assert {error.field for error in transaction.errors} == {
        "amount",
        "currency",
        "timestamp",
        "status",
    }


def test_missing_fields_accumulate_all_required_field_errors():
    transaction = normalize_record({"id": "A-1"})

    assert transaction.is_valid is False
    assert {error.field for error in transaction.errors} == {
        "amount",
        "currency",
        "timestamp",
        "status",
    }


def test_overflowing_date_invalidates_record_without_raising():
    transaction = normalize_record(
        {
            "id": "A-1",
            "amount": JsonNumber("10.00"),
            "currency": "USD",
            "timestamp": "0001-01-01T00:00:00+23:00",
            "status": "success",
        }
    )

    assert transaction.is_valid is False
    assert [error.code for error in transaction.errors] == [
        "DATE_NORMALIZATION_FAILED"
    ]
