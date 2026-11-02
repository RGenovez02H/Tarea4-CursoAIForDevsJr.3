from collections import Counter
from decimal import Decimal, localcontext
from typing import Iterable

from app.schemas.transaction import Transaction
from app.services.configuration import get_config


def calculate_metrics(transactions: Iterable[Transaction]) -> dict[str, object]:
    records = list(transactions)
    valid_count = sum(transaction.is_valid for transaction in records)
    invalid_count = len(records) - valid_count
    duplicate_count = sum(transaction.is_duplicate for transaction in records)

    canonical_states = get_config()["canonical_states"]
    status_counts = Counter(
        transaction.status
        for transaction in records
        if transaction.is_valid
        and not transaction.is_duplicate
        and transaction.status is not None
    )
    amounts_by_currency: dict[str, list[Decimal]] = {}
    for transaction in records:
        if (
            transaction.is_valid
            and not transaction.is_duplicate
            and transaction.amount is not None
            and transaction.currency is not None
        ):
            amounts_by_currency.setdefault(transaction.currency, []).append(
                transaction.amount
            )

    totals: dict[str, Decimal] = {}
    for currency, amounts in amounts_by_currency.items():
        nonzero_amounts = [amount for amount in amounts if amount]
        integer_digits = max(
            (max(amount.adjusted() + 1, 0) for amount in nonzero_amounts),
            default=1,
        )
        decimal_places = max(
            (max(-amount.as_tuple().exponent, 0) for amount in amounts),
            default=0,
        )
        carry_digits = len(str(len(amounts) - 1)) if len(amounts) > 1 else 0
        precision = max(1, integer_digits) + decimal_places + carry_digits
        with localcontext() as context:
            context.prec = precision
            totals[currency] = sum(amounts, Decimal("0"))

    validity_percentage = (
        Decimal(valid_count) * Decimal("100") / Decimal(len(records))
        if records
        else Decimal("0")
    )
    return {
        "total_processed": len(records),
        "total_valid": valid_count,
        "total_invalid": invalid_count,
        "total_duplicates": duplicate_count,
        "validity_percentage": str(validity_percentage),
        "count_by_status": {
            status: status_counts.get(status, 0) for status in canonical_states
        },
        "totals_by_currency": {
            currency: str(amount) for currency, amount in sorted(totals.items())
        },
    }
