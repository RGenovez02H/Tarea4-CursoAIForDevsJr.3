from decimal import Decimal

from app.repositories.memory_store import MemoryStore
from app.services.metrics import calculate_metrics
from app.services.normalizer import normalize_record


def format_1_record(identifier, amount="10.25", currency="USD", status="success"):
    return {
        "id": identifier,
        "amount": amount,
        "currency": currency,
        "timestamp": "2026-10-29T14:30:00Z",
        "status": status,
    }


def test_duplicates_are_source_local_trimmed_and_accumulate_between_uploads():
    store = MemoryStore()
    first = normalize_record(format_1_record(" TX-1 "))
    same_source_duplicate = normalize_record(format_1_record("TX-1"))
    other_source_same_id = normalize_record(
        {
            "transaction_id": "TX-1",
            "total": "5.00",
            "currency_code": "EUR",
            "created_at": "2026-10-29",
            "state": "PENDING",
        }
    )

    stored_first = store.add_many([first])
    stored_second_batch = store.add_many([same_source_duplicate, other_source_same_id])

    assert stored_first[0].is_duplicate is False
    assert stored_second_batch[0].is_duplicate is True
    assert stored_second_batch[1].is_duplicate is False
    assert len(store.get_all()) == 3


def test_invalid_duplicate_is_retained_and_duplicate_is_independent_of_validity():
    store = MemoryStore()
    invalid = normalize_record(format_1_record("A", amount="-1"))
    duplicate_invalid = normalize_record(format_1_record(" A ", amount="-2"))

    stored = store.add_many([invalid, duplicate_invalid])

    assert stored[0].is_valid is False
    assert stored[0].is_duplicate is False
    assert stored[1].is_valid is False
    assert stored[1].is_duplicate is True


def test_metrics_exclude_invalid_and_duplicates_from_financial_totals_and_states():
    store = MemoryStore()
    store.add_many(
        [
            normalize_record(format_1_record("A", "10.25", "USD", "success")),
            normalize_record(format_1_record(" A ", "10.25", "USD", "failed")),
            normalize_record(format_1_record("B", "-4.00", "USD", "success")),
            normalize_record(
                {
                    "id": "C",
                    "amount": "7.00",
                    "currency": "GTQ",
                    "timestamp": "2026-10-29",
                    "status": "pending",
                }
            ),
        ]
    )

    metrics = calculate_metrics(store.get_all())

    assert metrics["total_processed"] == 4
    assert metrics["total_valid"] == 3
    assert metrics["total_invalid"] == 1
    assert metrics["total_duplicates"] == 1
    assert metrics["count_by_status"] == {
        "PENDING": 1,
        "SUCCESS": 1,
        "FAILED": 0,
        "CANCELLED": 0,
    }
    assert metrics["totals_by_currency"] == {"GTQ": "7.00", "USD": "10.25"}


def test_clear_removes_records_and_duplicate_history():
    store = MemoryStore()
    store.add_many([normalize_record(format_1_record("A"))])

    assert store.clear() == 1
    assert store.get_all() == []
    restarted_identifier = store.add_many(
        [normalize_record(format_1_record("A"))]
    )[0]
    assert restarted_identifier.is_duplicate is False


def test_metrics_with_no_records_have_zero_counts():
    metrics = calculate_metrics([])

    assert metrics["total_processed"] == 0
    assert metrics["validity_percentage"] == "0"
    assert metrics["totals_by_currency"] == {}


def test_large_financial_totals_are_exact_without_decimal_rounding():
    amount = "99999999999999999999999999.99"
    transactions = [
        normalize_record(format_1_record("A", amount)),
        normalize_record(format_1_record("B", amount)),
    ]

    metrics = calculate_metrics(transactions)

    assert metrics["totals_by_currency"]["USD"] == (
        "199999999999999999999999999.98"
    )


def test_totals_remain_exact_and_separate_for_each_currency():
    transactions = [
        normalize_record(format_1_record("A", "99999999999999999999999999.99")),
        normalize_record(
            {
                "transaction_id": "B",
                "total": "99999999999999999999999999.99",
                "currency_code": "EUR",
                "created_at": "2026-10-29",
                "state": "COMPLETED",
            }
        ),
    ]

    metrics = calculate_metrics(transactions)

    assert metrics["totals_by_currency"] == {
        "EUR": "99999999999999999999999999.99",
        "USD": "99999999999999999999999999.99",
    }
