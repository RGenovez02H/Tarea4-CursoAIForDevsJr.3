from copy import deepcopy
from threading import RLock
from typing import Iterable

from app.schemas.transaction import Transaction
from app.services.normalizer import is_duplicate_key


class MemoryStore:
    def __init__(self) -> None:
        self._transactions: list[Transaction] = []
        self._seen_identifiers: set[tuple[str, str]] = set()
        self._lock = RLock()

    def add_many(self, transactions: Iterable[Transaction]) -> list[Transaction]:
        added: list[Transaction] = []
        with self._lock:
            for transaction in transactions:
                stored = deepcopy(transaction)
                duplicate_key = is_duplicate_key(stored)
                if duplicate_key is not None:
                    stored.is_duplicate = duplicate_key in self._seen_identifiers
                    self._seen_identifiers.add(duplicate_key)
                self._transactions.append(stored)
                added.append(deepcopy(stored))
        return added

    def get_all(self) -> list[Transaction]:
        with self._lock:
            return deepcopy(self._transactions)

    def find_by_identifier(
        self, transaction_id: str, source: str | None = None
    ) -> list[Transaction]:
        with self._lock:
            return [
                deepcopy(transaction)
                for transaction in self._transactions
                if transaction.transaction_id == transaction_id
                and (source is None or transaction.source == source)
            ]

    def clear(self) -> int:
        with self._lock:
            removed_count = len(self._transactions)
            self._transactions.clear()
            self._seen_identifiers.clear()
            return removed_count
