from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class ValidationError:
    field: str
    code: str
    message: str


@dataclass
class Transaction:
    transaction_id: str | None
    source: str
    amount: Decimal | None
    currency: str | None
    timestamp: str | None
    status: str | None
    is_valid: bool
    is_duplicate: bool = False
    errors: list[ValidationError] = field(default_factory=list)
    source_payload: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "transaction_id": self.transaction_id,
            "source": self.source,
            "amount": str(self.amount) if self.amount is not None else None,
            "currency": self.currency,
            "timestamp": self.timestamp,
            "status": self.status,
            "is_valid": self.is_valid,
            "is_duplicate": self.is_duplicate,
            "errors": [
                {
                    "field": error.field,
                    "code": error.code,
                    "message": error.message,
                }
                for error in self.errors
            ],
            "source_payload": self.source_payload,
        }
