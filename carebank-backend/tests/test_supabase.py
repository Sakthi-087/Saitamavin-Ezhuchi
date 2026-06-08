from __future__ import annotations

import unittest

import httpx

from app.core.config import Settings
from app.models.schemas import ManualTransactionRequest, Transaction, UserContext
from app.services.supabase import SupabaseService
from app.services.transaction_utils import normalize_transaction


class SupabaseServiceTests(unittest.TestCase):
    def test_server_errors_can_fallback_when_enabled(self) -> None:
        settings = Settings()
        settings.enable_sample_data_fallback = True
        service = SupabaseService(settings)
        response = httpx.Response(status_code=503, request=httpx.Request("GET", "https://example.com"))

        self.assertTrue(service._should_fallback_to_sample_data(response))

    def test_transaction_normalization_preserves_income_as_negative(self) -> None:
        transaction = Transaction(date="2026-03-01", description="Salary", amount=80000, category="Income")

        normalized = normalize_transaction(transaction)

        self.assertEqual(normalized.amount, -80000)

    def test_build_manual_transaction_row_normalizes_values(self) -> None:
        settings = Settings()
        service = SupabaseService(settings)
        payload = ManualTransactionRequest(
            date="2026-04-09",
            description="  Coffee shop  ",
            amount=245.5,
            category="Food",
        )
        user = UserContext(id="user-123", email="demo@example.com")

        row = service.build_manual_transaction_row(payload, user)

        self.assertEqual(row["user_id"], "user-123")
        self.assertEqual(row["amount"], 245.5)
        self.assertEqual(row["category"], "Food")
        self.assertEqual(row["description"], "Coffee shop")
        self.assertTrue(str(row["created_at"]).startswith("2026-04-09"))
        self.assertNotIn("metadata", row)
        self.assertNotIn("category_confidence", row)
        self.assertNotIn("raw_amount", row)
