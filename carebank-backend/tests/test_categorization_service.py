import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx

from app.services.categorization_service import AICategorizationService, CategorizationService


class TestCategorizationService(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        (self.root / "data").mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _service(self, *, ai_enabled: bool = False) -> CategorizationService:
        return CategorizationService(self.root, ai_enabled=ai_enabled)

    async def test_precedence_and_metadata(self):
        service = self._service()
        result = await service.categorize_async(user_id="u1", description="POS-ZOMATO-PAYMENT")
        self.assertEqual(result.category, "Food")
        self.assertEqual(result.source, "merchant_mapping")
        self.assertTrue(result.matched_rule.startswith("merchant:"))

    async def test_user_override_persists(self):
        service = self._service()
        first = await service.categorize_async(user_id="u2", description="RAZORPAY*UNKNOWN", user_category="Bills")
        second = await service.categorize_async(user_id="u2", description="RAZORPAY*UNKNOWN")
        self.assertEqual(first.category, "Bills")
        self.assertEqual(second.source, "learned_override")

    async def test_user_isolation_for_overrides(self):
        service = self._service()
        await service.categorize_async(user_id="user-a", description="Coffee Corner", user_category="Food")
        second = await service.categorize_async(user_id="user-b", description="Coffee Corner")
        self.assertNotEqual(second.source, "learned_override")

    async def test_empty_merchant_key_does_not_persist_override(self):
        service = self._service()
        first = await service.categorize_async(user_id="u3", description="PAYMENT INDIA PVT LTD", user_category="Bills")
        second = await service.categorize_async(user_id="u3", description="PAYMENT INDIA PVT LTD")
        self.assertEqual(first.source, "user_provided")
        self.assertNotEqual(second.source, "learned_override")

    def test_merchant_normalization_examples(self):
        service = self._service()
        self.assertEqual(service.resolve_merchant_key("UPI/PAYTM/SWIGGY/ORDER123"), "swiggy")
        self.assertEqual(service.resolve_merchant_key("POS-ZOMATO-PAYMENT"), "zomato")
        self.assertEqual(service.resolve_merchant_key("NETFLIX AUTOPAY"), "netflix")
        self.assertEqual(service.resolve_merchant_key("Paid to Uber India"), "uber")
        self.assertEqual(service.resolve_merchant_key("AMAZON PAY INDIA"), "amazon")

    async def test_known_merchant_does_not_call_ai(self):
        service = self._service(ai_enabled=True)
        service.ai.categorize = AsyncMock(return_value=None)
        result = await service.categorize_async(user_id="u1", description="NETFLIX AUTOPAY")
        self.assertEqual(result.source, "merchant_mapping")
        service.ai.categorize.assert_not_awaited()

    async def test_learned_override_does_not_call_ai(self):
        service = self._service(ai_enabled=True)
        service.ai.categorize = AsyncMock(return_value=None)
        await service.categorize_async(user_id="u9", description="Coffee", user_category="Food")
        result = await service.categorize_async(user_id="u9", description="Coffee")
        self.assertEqual(result.source, "learned_override")
        service.ai.categorize.assert_not_awaited()

    async def test_user_provided_category_does_not_call_ai(self):
        service = self._service(ai_enabled=True)
        service.ai.categorize = AsyncMock(return_value=None)
        result = await service.categorize_async(user_id="u10", description="Unknown Vendor", user_category="Bills")
        self.assertEqual(result.source, "user_provided")
        service.ai.categorize.assert_not_awaited()

    async def test_ai_disabled_does_not_call_ai(self):
        service = self._service(ai_enabled=False)
        service.ai.categorize = AsyncMock(return_value=None)
        result = await service.categorize_async(user_id="u11", description="XQZV Merchant")
        self.assertEqual(result.category, "Uncategorized")
        service.ai.categorize.assert_not_awaited()
        self.assertFalse(service.ai.enabled)

    async def test_ai_enabled_unknown_calls_ai(self):
        service = self._service(ai_enabled=True)
        service.ai.categorize = AsyncMock(
            return_value=service.categorize_sync(user_id="u12", description="SWIGGY FOOD")
        )
        result = await service.categorize_async(user_id="u12", description="XQZV Merchant")
        self.assertEqual(result.category, "Food")
        self.assertEqual(result.source, "merchant_mapping")
        service.ai.categorize.assert_awaited_once()

    async def test_timeout_or_api_failure_returns_uncategorized(self):
        service = self._service(ai_enabled=True)
        service.ai.categorize = AsyncMock(return_value=None)
        result = await service.categorize_async(user_id="u13", description="No Match Merchant")
        self.assertEqual(result.category, "Uncategorized")
        self.assertEqual(result.source, "fallback")

    async def test_sync_contract_is_deterministic_only(self):
        service = self._service(ai_enabled=True)
        service.ai.categorize = AsyncMock(return_value=None)
        result = service.categorize_sync(user_id="u14", description="No Match Merchant")
        self.assertEqual(result.category, "Uncategorized")
        self.assertEqual(result.source, "fallback")

    def test_no_asyncio_run_present(self):
        root = Path(__file__).resolve().parents[1]
        for py_file in root.joinpath("app").rglob("*.py"):
            text = py_file.read_text(encoding="utf-8")
            self.assertNotIn("asyncio.run(", text)


class _MockResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class _MockAsyncClient:
    def __init__(self, response: _MockResponse | None = None, error: Exception | None = None, **_: object) -> None:
        self.response = response
        self.error = error

    async def __aenter__(self) -> "_MockAsyncClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def post(self, *args, **kwargs):
        if self.error:
            raise self.error
        return self.response


class TestAICategorizationService(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.original_key = os.environ.get("OPENROUTER_API_KEY")
        os.environ["OPENROUTER_API_KEY"] = "test-key"

    def tearDown(self) -> None:
        if self.original_key is None:
            os.environ.pop("OPENROUTER_API_KEY", None)
        else:
            os.environ["OPENROUTER_API_KEY"] = self.original_key

    async def test_malformed_ai_json_returns_none(self):
        svc = AICategorizationService(enabled=True, model="test-model")
        payload = {"choices": [{"message": {"content": "not json"}}]}
        with patch("app.services.categorization_service.httpx.AsyncClient", return_value=_MockAsyncClient(response=_MockResponse(payload))):
            result = await svc.categorize("Unknown")
        self.assertIsNone(result)

    async def test_timeout_returns_none(self):
        svc = AICategorizationService(enabled=True, model="test-model")
        err = httpx.TimeoutException("timeout", request=httpx.Request("POST", "https://example.com"))
        with patch("app.services.categorization_service.httpx.AsyncClient", return_value=_MockAsyncClient(error=err)):
            result = await svc.categorize("Unknown")
        self.assertIsNone(result)

    async def test_invalid_ai_confidence_falls_back_safely(self):
        svc = AICategorizationService(enabled=True, model="test-model")
        payload = {
            "choices": [
                {"message": {"content": '{"category":"Food","subcategory":"Dining","confidence":"abc","reason":"x"}'}}
            ]
        }
        with patch("app.services.categorization_service.httpx.AsyncClient", return_value=_MockAsyncClient(response=_MockResponse(payload))):
            result = await svc.categorize("Unknown")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
