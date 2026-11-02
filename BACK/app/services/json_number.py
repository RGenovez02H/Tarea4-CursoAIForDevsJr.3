from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class JsonNumber:
    raw: str

    def as_decimal(self) -> Decimal:
        return Decimal(self.raw)
