from __future__ import annotations

import csv
import io
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import httpx
from fastapi import HTTPException, status

from app.core.config import Settings
from app.models.schemas import ManualTransactionRequest, Transaction, UserContext
from app.services.categorization_service import CategorizationService
from app.services.transaction_utils import normalize_transaction

logger = logging.getLogger(__name__)
DEV_AUTH_PREFIX = "carebank-dev:"


def _dev_email_from_token(token: str) -> str:
    if token.startswith(DEV_AUTH_PREFIX):
        value = token[len(DEV_AUTH_PREFIX) :].strip()
        if value.startswith("refresh:"):
            value = value[len("refresh:") :].strip()
        return value or "demo@carebank.local"
    return ""


class SupabaseService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.categorization = CategorizationService(
            Path(__file__).resolve().parents[2],
            ai_enabled=settings.ai_categorization_enabled,
            ai_model=settings.ai_categorization_model,
        )

    async def verify_access_token(self, access_token: str) -> UserContext:
        if self.settings.enable_sample_data_fallback and not self.settings.is_production and access_token.startswith(DEV_AUTH_PREFIX):
            email = _dev_email_from_token(access_token)
            safe_id = f"dev_{''.join(ch if ch.isalnum() else '_' for ch in email.lower()).strip('_') or 'user'}"
            return UserContext(id=safe_id, email=email)

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(
                    f"{self.settings.supabase_url}/auth/v1/user",
                    headers=self._headers(access_token),
                )
        except httpx.RequestError as exc:
            logger.exception("Supabase auth request failed while verifying the access token.")
            raise self._service_unavailable("Supabase auth is currently unavailable.", exc) from exc

        if response.status_code != status.HTTP_200_OK:
            logger.warning(
                "Supabase auth returned a non-200 response while verifying the access token: status=%s body=%s",
                response.status_code,
                response.text[:300],
            )
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired Supabase token.")

        payload = response.json()
        return UserContext(id=payload["id"], email=payload.get("email"))

    async def fetch_transactions(self, access_token: str) -> list[Transaction]:
        payload = await self.fetch_transaction_history(access_token)
        transactions: list[Transaction] = []
        for item in payload:
            created_at = item.get("created_at") or datetime.now(UTC).isoformat()
            transactions.append(
                normalize_transaction(
                    Transaction(
                        date=str(created_at)[:10],
                        description=item.get("description") or "Imported transaction",
                        amount=float(item.get("amount") or 0),
                        category=item.get("category") or "Uncategorized",
                    )
                )
            )
        return transactions

    async def fetch_transaction_history(self, access_token: str) -> list[dict[str, object]]:
        if self.settings.enable_sample_data_fallback and not self.settings.is_production and access_token.startswith(DEV_AUTH_PREFIX):
            logger.info("Using sample transactions for development auth session.")
            return self._load_sample_transactions()

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(
                    f"{self.settings.supabase_url}/rest/v1/transactions",
                    params={
                        "select": "amount,category,description,created_at,fraud_risk,fraud_flags",
                        "order": "created_at.asc",
                    },
                    headers=self._headers(access_token),
                )
        except httpx.RequestError as exc:
            logger.exception("Supabase transactions request failed while fetching history.")
            if self.settings.enable_sample_data_fallback:
                logger.warning("Falling back to sample transactions because ENABLE_SAMPLE_DATA_FALLBACK is enabled.")
                return self._load_sample_transactions()
            raise self._service_unavailable("Failed to reach Supabase transactions API.", exc) from exc

        if self._should_fallback_to_sample_data(response):
            logger.warning(
                "Supabase transactions API returned a recoverable server error. Falling back to sample data."
            )
            return self._load_sample_transactions()

        self._raise_for_supabase_error(response, "Failed to fetch transactions from Supabase.")
        return response.json()

    async def insert_transactions(self, access_token: str, rows: list[dict[str, object]]) -> int:
        if not rows:
            return 0

        if self.settings.enable_sample_data_fallback and not self.settings.is_production and access_token.startswith(DEV_AUTH_PREFIX):
            logger.info("Skipping remote transaction insert for development auth session.")
            return len(rows)

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.settings.supabase_url}/rest/v1/transactions",
                headers={
                    **self._headers(access_token),
                    "Content-Type": "application/json",
                    "Prefer": "return=representation",
                },
                json=rows,
            )

        self._raise_for_supabase_error(response, "Failed to insert transactions into Supabase.")
        return len(response.json())

    async def persist_behavior_snapshot(
        self,
        access_token: str,
        *,
        user_id: str,
        snapshot: dict[str, object],
    ) -> None:
        payload = [
            {
                "user_id": user_id,
                "snapshot": snapshot,
                "created_at": datetime.now(UTC).isoformat(),
            }
        ]
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{self.settings.supabase_url}/rest/v1/behavior_snapshots",
                    headers={
                        **self._headers(access_token),
                        "Content-Type": "application/json",
                        "Prefer": "return=minimal",
                    },
                    json=payload,
                )
        except httpx.RequestError:
            logger.warning("Behavior snapshot persistence skipped due to Supabase request error.")
            return

        if response.is_success:
            return

        detail = response.text[:200]
        try:
            body = response.json()
            detail = str(body.get("message") or body.get("error") or body.get("error_description") or detail)
        except ValueError:
            pass

        if response.status_code in {400, 404}:
            logger.warning("Behavior snapshot persistence skipped (table may be missing): %s", detail)
            return

        logger.warning("Behavior snapshot persistence failed with status=%s detail=%s", response.status_code, detail)

    async def persist_risk_snapshot(
        self,
        access_token: str,
        *,
        user_id: str,
        snapshot: dict[str, object],
    ) -> None:
        payload = [
            {
                "user_id": user_id,
                "snapshot": snapshot,
                "created_at": datetime.now(UTC).isoformat(),
            }
        ]
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{self.settings.supabase_url}/rest/v1/risk_snapshots",
                    headers={
                        **self._headers(access_token),
                        "Content-Type": "application/json",
                        "Prefer": "return=minimal",
                    },
                    json=payload,
                )
        except httpx.RequestError:
            logger.warning("Risk snapshot persistence skipped due to Supabase request error.")
            return

        if response.is_success:
            return

        detail = response.text[:200]
        try:
            body = response.json()
            detail = str(body.get("message") or body.get("error") or body.get("error_description") or detail)
        except ValueError:
            pass

        if response.status_code in {400, 404}:
            logger.warning("Risk snapshot persistence skipped (table may be missing): %s", detail)
            return
        logger.warning("Risk snapshot persistence failed with status=%s detail=%s", response.status_code, detail)

    async def persist_guidance_snapshot(
        self,
        access_token: str,
        *,
        user_id: str,
        snapshot: dict[str, object],
    ) -> None:
        payload = [
            {
                "user_id": user_id,
                "snapshot": snapshot,
                "created_at": datetime.now(UTC).isoformat(),
            }
        ]
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{self.settings.supabase_url}/rest/v1/guidance_snapshots",
                    headers={**self._headers(access_token), "Content-Type": "application/json", "Prefer": "return=minimal"},
                    json=payload,
                )
        except httpx.RequestError:
            logger.warning("Guidance snapshot persistence skipped due to Supabase request error.")
            return
        if response.is_success:
            return
        if response.status_code in {400, 404}:
            logger.warning("Guidance snapshot persistence skipped (table may be missing).")
            return
        logger.warning("Guidance snapshot persistence failed with status=%s", response.status_code)

    async def persist_guidance_items(
        self,
        access_token: str,
        *,
        user_id: str,
        items: list[dict[str, object]],
    ) -> None:
        if not items:
            return
        payload = []
        for item in items:
            payload.append(
                {
                    "user_id": user_id,
                    "guidance_id": item.get("guidance_id"),
                    "guidance_type": item.get("guidance_type"),
                    "priority": item.get("priority"),
                    "confidence": item.get("confidence"),
                    "actionability_score": item.get("actionability_score"),
                    "title": item.get("title"),
                    "rationale": item.get("rationale"),
                    "action_steps": item.get("action_steps"),
                    "expected_impact": item.get("expected_impact"),
                    "source_signals": item.get("source_signals"),
                    "related_risk_events": item.get("related_risk_events"),
                    "ttl_days": item.get("ttl_days"),
                    "created_at": item.get("created_at") or datetime.now(UTC).isoformat(),
                }
            )
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{self.settings.supabase_url}/rest/v1/guidance_items",
                    headers={**self._headers(access_token), "Content-Type": "application/json", "Prefer": "return=minimal"},
                    json=payload,
                )
        except httpx.RequestError:
            logger.warning("Guidance items persistence skipped due to Supabase request error.")
            return
        if response.is_success:
            return
        if response.status_code in {400, 404}:
            logger.warning("Guidance items persistence skipped (table may be missing).")
            return
        logger.warning("Guidance items persistence failed with status=%s", response.status_code)

    async def persist_financial_score_snapshot(
        self,
        access_token: str,
        *,
        user_id: str,
        snapshot: dict[str, object],
    ) -> None:
        payload = [
            {
                "user_id": user_id,
                "created_at": datetime.now(UTC).isoformat(),
                "score": snapshot.get("score"),
                "status": snapshot.get("status"),
                "scoring_version": snapshot.get("scoring_version"),
                "confidence": snapshot.get("confidence"),
                "explainability": snapshot.get("explainability"),
                "snapshot": snapshot,
            }
        ]
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{self.settings.supabase_url}/rest/v1/financial_score_snapshots",
                    headers={**self._headers(access_token), "Content-Type": "application/json", "Prefer": "return=minimal"},
                    json=payload,
                )
        except httpx.RequestError:
            logger.warning("Financial score snapshot persistence skipped due to Supabase request error.")
            return
        if response.is_success:
            return
        if response.status_code in {400, 404}:
            logger.warning("Financial score snapshot persistence skipped (table may be missing).")
            return
        logger.warning("Financial score snapshot persistence failed with status=%s", response.status_code)

    async def parse_csv_upload(self, content: str, user: UserContext) -> tuple[list[dict[str, object]], list[str]]:
        try:
            sample = content[:1024]
            dialect = csv.Sniffer().sniff(sample)
        except csv.Error:
            dialect = csv.excel

        reader = csv.DictReader(io.StringIO(content), dialect=dialect)
        rows: list[dict[str, object]] = []
        errors: list[str] = []

        for index, record in enumerate(reader, start=2):
            try:
                created_at = self._parse_date(self._pick_required(record, ["date", "created_at", "transaction_date", "posted_at"]))
                amount = self._parse_amount(self._pick_required(record, ["amount", "value", "amt", "debit", "credit"]))
                description = self._pick_optional(record, ["description", "details", "narration", "merchant"]) or "Imported transaction"
                provided_category = self._pick_optional(record, ["category", "type"]) or None
                row = await self.build_transaction_row_async(
                    user=user,
                    created_at=created_at,
                    amount=amount,
                    description=description,
                    category=provided_category,
                )
                rows.append(row)
            except ValueError as exc:
                errors.append(f"Row {index}: {exc}")

        return rows, errors

    def build_manual_transaction_row(self, payload: ManualTransactionRequest, user: UserContext) -> dict[str, object]:
        return self.build_transaction_row(
            user=user,
            created_at=self._parse_date(payload.date),
            amount=payload.amount,
            description=payload.description,
            category=payload.category,
        )

    def build_transaction_row(
        self,
        *,
        user: UserContext,
        created_at: str,
        amount: float,
        description: str,
        category: str | None = None,
    ) -> dict[str, object]:
        normalized_description = description.strip() or "Imported transaction"
        category_result = self.categorization.categorize_sync(
            user_id=user.id,
            description=normalized_description,
            user_category=(category or "").strip() or None,
        )
        raw_amount = float(amount)
        normalized_amount = abs(raw_amount)
        tx_type = "credit" if raw_amount > 0 else "debit"
        return {
            "user_id": user.id,
            "amount": normalized_amount,
            "transaction_type": tx_type,
            "category": category_result.category,
            "metadata": {
                "raw_amount": raw_amount,
                "normalized_amount": normalized_amount,
                "subcategory": category_result.subcategory,
                "category_confidence": category_result.confidence,
                "category_source": category_result.source,
                "category_matched_rule": category_result.matched_rule,
                "category_reason": category_result.reason,
            },
            "description": normalized_description,
            "created_at": created_at,
        }

    async def build_transaction_row_async(
        self,
        *,
        user: UserContext,
        created_at: str,
        amount: float,
        description: str,
        category: str | None = None,
    ) -> dict[str, object]:
        normalized_description = description.strip() or "Imported transaction"
        category_result = await self.categorization.categorize_async(
            user_id=user.id,
            description=normalized_description,
            user_category=(category or "").strip() or None,
        )
        raw_amount = float(amount)
        normalized_amount = abs(raw_amount)
        tx_type = "credit" if raw_amount > 0 else "debit"
        return {
            "user_id": user.id,
            "amount": normalized_amount,
            "transaction_type": tx_type,
            "category": category_result.category,
            "metadata": {
                "raw_amount": raw_amount,
                "normalized_amount": normalized_amount,
                "subcategory": category_result.subcategory,
                "category_confidence": category_result.confidence,
                "category_source": category_result.source,
                "category_matched_rule": category_result.matched_rule,
                "category_reason": category_result.reason,
            },
            "description": normalized_description,
            "created_at": created_at,
        }

    def _headers(self, access_token: str) -> dict[str, str]:
        return {
            "apikey": self.settings.supabase_anon_key,
            "Authorization": f"Bearer {access_token}",
        }

    def _service_role_headers(self) -> dict[str, str]:
        return {
            "apikey": self.settings.supabase_service_role_key,
            "Authorization": f"Bearer {self.settings.supabase_service_role_key}",
        }

    def _pick_required(self, record: dict[str, str | None], keys: list[str]) -> str:
        normalized = {str(key).strip().lower(): (value or "").strip() for key, value in record.items() if key}
        for key in keys:
            value = normalized.get(key)
            if value:
                return value
        raise ValueError(f"Missing one of the required CSV columns: {', '.join(keys)}")

    def _pick_optional(self, record: dict[str, str | None], keys: list[str]) -> str:
        normalized = {str(key).strip().lower(): (value or "").strip() for key, value in record.items() if key}
        for key in keys:
            value = normalized.get(key)
            if value:
                return value
        return ""

    def _parse_date(self, value: str) -> str:
        cleaned = value.strip()
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"):
            try:
                parsed = datetime.strptime(cleaned, fmt)
                return parsed.replace(tzinfo=UTC).isoformat()
            except ValueError:
                continue

        try:
            parsed = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC).isoformat()
        except ValueError as exc:
            raise ValueError(f"Invalid date '{value}'.") from exc

    def _parse_amount(self, value: str) -> float:
        cleaned = value.replace(",", "").replace("Rs.", "").replace("Rs", "").replace("INR", "").strip()
        if cleaned.startswith("(") and cleaned.endswith(")"):
            cleaned = f"-{cleaned[1:-1]}"
        try:
            return float(cleaned)
        except ValueError as exc:
            raise ValueError(f"Invalid amount '{value}'.") from exc

    def _raise_for_supabase_error(self, response: httpx.Response, message: str) -> None:
        if response.is_success:
            return

        detail = message
        try:
            payload = response.json()
            detail = payload.get("message") or payload.get("error_description") or payload.get("error") or message
        except ValueError:
            pass

        logger.warning(
            "Supabase API returned a non-success response: status=%s detail=%s body=%s",
            response.status_code,
            detail,
            response.text[:300],
        )

        raise HTTPException(status_code=response.status_code, detail=detail)

    def _should_fallback_to_sample_data(self, response: httpx.Response) -> bool:
        return self.settings.enable_sample_data_fallback and response.status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR

    def _service_unavailable(self, message: str, exc: httpx.RequestError) -> HTTPException:
        request_url = str(exc.request.url) if exc.request else "Supabase"
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"{message} Request target: {request_url}.",
        )

    def _load_sample_transactions(self) -> list[dict[str, object]]:
        sample_path = Path(__file__).resolve().parents[2] / "data" / "transactions.json"
        with sample_path.open("r", encoding="utf-8") as sample_file:
            payload = json.load(sample_file)

        return [
            {
                "amount": item.get("amount", 0),
                "category": item.get("category", "Uncategorized"),
                "description": item.get("description", "Imported transaction"),
                "created_at": item.get("date", datetime.now(UTC).date().isoformat()),
                "fraud_risk": item.get("fraud_risk", "Low"),
                "fraud_flags": item.get("fraud_flags", []),
            }
            for item in payload
        ]

    async def persist_system_event_service(self, payload: dict[str, object]) -> bool:
        return await self._persist_service_role("system_events", payload)

    async def persist_processing_event_service(self, payload: dict[str, object]) -> bool:
        return await self._persist_service_role("processing_events", payload)

    async def persist_live_alert_event_service(self, payload: dict[str, object]) -> bool:
        return await self._persist_service_role("live_alert_events", payload)

    async def persist_dead_letter_event_service(self, payload: dict[str, object]) -> bool:
        return await self._persist_service_role("dead_letter_events", payload)

    async def persist_event_replay_history_service(self, payload: dict[str, object]) -> bool:
        return await self._persist_service_role("event_replay_history", payload)

    async def persist_audit_log_service(self, payload: dict[str, object]) -> bool:
        return await self._persist_service_role("audit_logs", payload)

    async def _persist_service_role(self, table: str, payload: dict[str, object]) -> bool:
        if not self.settings.enable_audit_persistence or not self.settings.supabase_service_role_configured:
            return False
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{self.settings.supabase_url}/rest/v1/{table}",
                    headers={**self._service_role_headers(), "Content-Type": "application/json", "Prefer": "return=minimal"},
                    json=[payload],
                )
        except httpx.RequestError:
            logger.warning("Service-role persistence failed for table=%s due to request error.", table)
            return False
        if response.is_success:
            return True
        logger.warning("Service-role persistence failed for table=%s status=%s", table, response.status_code)
        return False

    async def get_financial_score_history(self, access_token: str, user_id: str, *, limit: int = 25) -> list[dict[str, object]]:
        return await self._get_user_history(
            access_token,
            table="financial_score_snapshots",
            user_id=user_id,
            limit=limit,
            select="id,score,status,scoring_version,confidence,created_at",
        )

    async def get_risk_event_history(self, access_token: str, user_id: str, *, limit: int = 25) -> list[dict[str, object]]:
        # Prefer dedicated risk_events table when available; fallback to risk_snapshots projections.
        rows = await self._get_user_history(
            access_token,
            table="risk_events",
            user_id=user_id,
            limit=limit,
            select="id,payload,created_at,correlation_id",
        )
        if rows:
            return rows
        return await self._get_user_history(
            access_token,
            table="risk_snapshots",
            user_id=user_id,
            limit=limit,
            select="id,snapshot,created_at,correlation_id",
        )

    async def get_guidance_history(self, access_token: str, user_id: str, *, limit: int = 25) -> list[dict[str, object]]:
        return await self._get_user_history(
            access_token,
            table="guidance_items",
            user_id=user_id,
            limit=limit,
            select="id,guidance_id,guidance_type,priority,title,confidence,actionability_score,created_at",
        )

    async def get_behavior_history(self, access_token: str, user_id: str, *, limit: int = 25) -> list[dict[str, object]]:
        return await self._get_user_history(
            access_token,
            table="behavior_snapshots",
            user_id=user_id,
            limit=limit,
            select="id,snapshot,created_at,correlation_id",
        )

    async def get_audit_history(self, access_token: str, user_id: str, *, limit: int = 25) -> list[dict[str, object]]:
        del access_token
        if not self.settings.supabase_service_role_configured:
            return []
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(
                    f"{self.settings.supabase_url}/rest/v1/audit_logs",
                    params={
                        "select": "id,audit_type,severity,created_at,metadata,user_id",
                        "order": "created_at.desc",
                        "limit": max(1, min(int(limit), 200)),
                        "or": f"(user_id.eq.{user_id},user_id.is.null)",
                    },
                    headers=self._service_role_headers(),
                )
        except httpx.RequestError:
            return []
        if not response.is_success:
            return []
        results: list[dict[str, object]] = []
        for row in response.json():
            meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
            results.append(
                {
                    "id": row.get("id"),
                    "audit_type": row.get("audit_type"),
                    "severity": row.get("severity"),
                    "created_at": row.get("created_at"),
                    "metadata": {"event_type": meta.get("event_type"), "correlation_id": meta.get("correlation_id")},
                }
            )
        return results

    async def _get_user_history(
        self,
        access_token: str,
        *,
        table: str,
        user_id: str,
        limit: int,
        select: str,
    ) -> list[dict[str, object]]:
        bounded_limit = max(1, min(int(limit), 200))
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(
                    f"{self.settings.supabase_url}/rest/v1/{table}",
                    params={
                        "select": select,
                        "user_id": f"eq.{user_id}",
                        "order": "created_at.desc",
                        "limit": bounded_limit,
                    },
                    headers=self._headers(access_token),
                )
        except httpx.RequestError:
            return []
        if not response.is_success:
            return []
        return response.json()
