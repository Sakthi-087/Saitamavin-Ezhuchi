from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from hashlib import sha1
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.auth import get_current_user
from app.core.config import get_settings
from app.models.schemas import (
    CsvUploadResponse,
    FraudFinding,
    ManualTransactionRequest,
    ManualTransactionResponse,
    SystemEvent,
    UserContext,
)
from app.services.event_bus import get_event_bus
from app.services.event_store import EventStore
from app.services.fraud import FraudDetectionService
from app.services.idempotency_store import IdempotencyStore
from app.services.rate_limiter import get_rate_limiter
from app.services.realtime_pipeline import get_realtime_pipeline
from app.services.supabase import SupabaseService
from pathlib import Path

router = APIRouter(tags=["transactions"])
security = HTTPBearer(auto_error=False)
fraud_service = FraudDetectionService()
event_store = EventStore(Path(__file__).resolve().parents[2])


def _make_event(*, event_type: str, user_id: str, correlation_id: str, payload: dict[str, object]) -> SystemEvent:
    raw = f"{event_type}:{user_id}:{correlation_id}:{uuid4().hex}"
    event_id = f"evt_{sha1(raw.encode('utf-8')).hexdigest()[:16]}"
    idempotency_key = IdempotencyStore.make_key(event_type, user_id, correlation_id, resource_id=str(payload.get("source") or "tx"))
    return SystemEvent(
        event_id=event_id,
        event_type=event_type,
        user_id=user_id,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        payload=payload,
        status="pending",
        attempt_count=0,
        max_attempts=3,
        created_at=datetime.now(UTC).isoformat(),
        updated_at=None,
    )


async def enrich_and_insert_transactions(
    *,
    service: SupabaseService,
    access_token: str,
    rows: list[dict[str, object]],
) -> tuple[int, list[FraudFinding]]:
    history = await service.fetch_transaction_history(access_token)
    fraud_summary: list[FraudFinding] = []
    enriched_rows: list[dict[str, object]] = []

    for row in rows:
        fraud_result = fraud_service.detect_fraud(history, row)
        enriched_row = {
            **row,
            "fraud_risk": fraud_result["risk"],
            "fraud_flags": fraud_result["flags"],
        }
        enriched_rows.append(enriched_row)
        history.append(enriched_row)

        if fraud_result["risk"] in {"Medium", "High"}:
            fraud_summary.append(
                FraudFinding(
                    description=str(row.get("description") or "Imported transaction"),
                    amount=round(abs(float(row.get("amount") or 0)), 2),
                    risk=fraud_result["risk"],
                    flags=[str(flag) for flag in fraud_result["flags"]],
                )
            )

    inserted_count = await service.insert_transactions(access_token, enriched_rows)
    return inserted_count, fraud_summary


@router.post("/transactions/upload-csv", response_model=CsvUploadResponse)
async def upload_transactions_csv(
    file: UploadFile = File(...),
    request: Request = None,
    user: UserContext = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> CsvUploadResponse:
    await get_rate_limiter().enforce(request, user.id)
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token.")
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please upload a CSV file.")

    service = SupabaseService(get_settings())
    raw_bytes = await file.read()

    try:
        content = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CSV file must be UTF-8 encoded.") from exc

    rows, errors = await service.parse_csv_upload(content, user)
    inserted_count, fraud_summary = await enrich_and_insert_transactions(
        service=service,
        access_token=credentials.credentials,
        rows=rows,
    )
    correlation_id = f"corr_{uuid4().hex[:12]}"
    event = _make_event(
        event_type="transaction_ingested",
        user_id=user.id,
        correlation_id=correlation_id,
        payload={"inserted_count": inserted_count, "source": "csv"},
    )
    event_store.persist_system_event(event)
    bus = get_event_bus()
    await bus.publish(event)
    asyncio.create_task(get_realtime_pipeline().process_event(event))

    return CsvUploadResponse(
        inserted_count=inserted_count,
        skipped_count=len(errors),
        errors=errors,
        fraud_summary=fraud_summary,
    )


@router.post("/transactions/manual", response_model=ManualTransactionResponse)
async def create_manual_transaction(
    payload: ManualTransactionRequest,
    request: Request,
    user: UserContext = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> ManualTransactionResponse:
    await get_rate_limiter().enforce(request, user.id)
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token.")

    service = SupabaseService(get_settings())
    row = await service.build_transaction_row_async(
        user=user,
        created_at=service._parse_date(payload.date),
        amount=payload.amount,
        description=payload.description,
        category=payload.category,
    )
    inserted_count, fraud_summary = await enrich_and_insert_transactions(
        service=service,
        access_token=credentials.credentials,
        rows=[row],
    )
    correlation_id = f"corr_{uuid4().hex[:12]}"
    event = _make_event(
        event_type="transaction_ingested",
        user_id=user.id,
        correlation_id=correlation_id,
        payload={"inserted_count": inserted_count, "source": "manual"},
    )
    event_store.persist_system_event(event)
    bus = get_event_bus()
    await bus.publish(event)
    asyncio.create_task(get_realtime_pipeline().process_event(event))
    return ManualTransactionResponse(inserted_count=inserted_count, fraud_summary=fraud_summary)
