import json
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from starlette.responses import Response

from app.repositories.memory_store import MemoryStore
from app.services.configuration import get_config
from app.services.metrics import calculate_metrics
from app.services.json_number import JsonNumber
from app.services.normalizer import normalize_record


router = APIRouter(prefix="/api")
store = MemoryStore()


def _encode_json(value: Any) -> str:
    if isinstance(value, JsonNumber):
        return value.raw
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("JSON no puede incluir números decimales no finitos.")
        return format(value, "f")
    if isinstance(value, dict):
        return "{" + ",".join(
            f"{json.dumps(str(key), ensure_ascii=False)}:{_encode_json(item)}"
            for key, item in value.items()
        ) + "}"
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_encode_json(item) for item in value) + "]"
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def _json_response(content: Any, status_code: int = 200) -> Response:
    return Response(
        content=_encode_json(content),
        status_code=status_code,
        media_type="application/json",
    )


def _parse_constant(value: str) -> None:
    raise ValueError(f"El valor '{value}' no es un número JSON válido.")


@router.post("/transactions/upload")
async def upload_transactions(request: Request) -> Response:
    body = await request.body()
    try:
        payload = json.loads(
            body,
            parse_float=JsonNumber,
            parse_constant=_parse_constant,
        )
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as error:
        raise HTTPException(status_code=400, detail=f"JSON inválido: {error}") from error

    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, dict):
        records = [payload]
    else:
        raise HTTPException(
            status_code=422,
            detail="El cuerpo JSON debe ser un objeto o una lista de objetos.",
        )

    added = store.add_many(normalize_record(record) for record in records)
    return _json_response(
        {
            "received": len(records),
            "added": len(added),
            "total_processed": len(store.get_all()),
            "transactions": [transaction.to_dict() for transaction in added],
        },
        status_code=201,
    )


def _transaction_response(validity: bool | None = None) -> Response:
    transactions = store.get_all()
    if validity is not None:
        transactions = [
            transaction
            for transaction in transactions
            if transaction.is_valid is validity
        ]
    return _json_response(
        [transaction.to_dict() for transaction in transactions]
    )


@router.get("/transactions")
async def get_transactions() -> Response:
    return _transaction_response()


@router.get("/transactions/valid")
async def get_valid_transactions() -> Response:
    return _transaction_response(True)


@router.get("/transactions/invalid")
async def get_invalid_transactions() -> Response:
    return _transaction_response(False)


@router.get("/transactions/search")
async def search_transactions(
    transaction_id: str, source: str | None = None
) -> Response:
    identifier = transaction_id.strip()
    if not identifier:
        raise HTTPException(status_code=422, detail="El identificador es obligatorio.")
    if source is not None and source not in get_config()["sources"]:
        raise HTTPException(status_code=422, detail="La fuente indicada no es válida.")
    matches = store.find_by_identifier(identifier, source)
    return _json_response([transaction.to_dict() for transaction in matches])


@router.get("/metrics")
async def get_metrics() -> Response:
    return _json_response(calculate_metrics(store.get_all()))


@router.get("/health")
async def get_health() -> Response:
    return _json_response({"status": "ok"})


@router.delete("/transactions")
async def clear_transactions() -> Response:
    removed_count = store.clear()
    return _json_response(
        {"cleared": removed_count, "total_processed": 0}
    )
