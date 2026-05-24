from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class CategorizationResult:
    category: str
    subcategory: str
    confidence: float
    source: str
    matched_rule: str
    reason: str


class CategorizationOverrideStore:
    def __init__(self, root_path: Path) -> None:
        self.path = root_path / "data" / "categorization_overrides.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def _load(self) -> dict[str, dict[str, str]]:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning("Override store contains invalid JSON; treating as empty.")
            return {}
        except OSError:
            logger.warning("Override store could not be read; treating as empty.")
            return {}

    def _save(self, payload: dict[str, dict[str, str]]) -> None:
        # File storage is kept for local/dev compatibility; a DB table is preferred for distributed production.
        temp_path = self.path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temp_path.replace(self.path)

    def get(self, user_id: str, merchant_key: str) -> str | None:
        with self._lock:
            payload = self._load()
            return payload.get(user_id, {}).get(merchant_key)

    def set(self, user_id: str, merchant_key: str, category: str) -> None:
        with self._lock:
            payload = self._load()
            payload.setdefault(user_id, {})[merchant_key] = category
            self._save(payload)


class AICategorizationService:
    def __init__(self, *, enabled: bool, model: str) -> None:
        self.enabled = enabled
        self.api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
        self.base_url = os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")
        self.model = model

    async def categorize(self, description: str) -> CategorizationResult | None:
        if not self.enabled:
            return None
        if not self.api_key:
            logger.info("AI categorization skipped: OPENROUTER_API_KEY missing.")
            return None
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "Return strict JSON: category,subcategory,confidence,reason."},
                {"role": "user", "content": f"Categorize transaction: {description}"},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.post(f"{self.base_url.rstrip('/')}/chat/completions", headers=headers, json=body)
                r.raise_for_status()
                payload = r.json()
                content = payload["choices"][0]["message"]["content"]
                data = json.loads(content)
                confidence_raw = data.get("confidence")
                confidence = float(confidence_raw) if confidence_raw is not None else 0.4
                if not (0 <= confidence <= 1):
                    logger.warning("AI categorization returned out-of-range confidence=%s; using safe fallback.", confidence)
                    confidence = 0.4
                return CategorizationResult(
                    category=str(data.get("category") or "Uncategorized"),
                    subcategory=str(data.get("subcategory") or "General"),
                    confidence=confidence,
                    source="ai_fallback",
                    matched_rule="ai:model",
                    reason=str(data.get("reason") or "AI fallback categorization"),
                )
        except httpx.HTTPError:
            logger.warning("AI categorization skipped due to HTTP error.")
            return None
        except TimeoutError:
            logger.warning("AI categorization skipped due to timeout.")
            return None
        except json.JSONDecodeError:
            logger.warning("AI categorization skipped due to malformed JSON response.")
            return None
        except ValueError:
            logger.warning("AI categorization skipped due to invalid value conversion.")
            return None
        except KeyError:
            logger.warning("AI categorization skipped due to missing response keys.")
            return None


class CategorizationService:
    GENERIC_TOKENS = {
        "UPI",
        "POS",
        "PAYTM",
        "PAYMENT",
        "AUTOPAY",
        "ORDER",
        "PAID",
        "TO",
        "INDIA",
        "PVT",
        "LTD",
        "PAY",
    }

    def __init__(self, root_path: Path, *, ai_enabled: bool = False, ai_model: str = "google/gemini-2.5-flash-lite") -> None:
        self.overrides = CategorizationOverrideStore(root_path)
        self.ai = AICategorizationService(enabled=ai_enabled, model=ai_model)
        self.merchant_map = {
            "SWIGGY": ("Food", "Delivery"),
            "ZOMATO": ("Food", "Dining"),
            "NETFLIX": ("Bills", "Subscription"),
            "UBER": ("Travel", "Cab"),
            "AMAZON": ("Shopping", "Marketplace"),
            "PAYTM": ("Bills", "Wallet"),
        }
        self.keyword_rules = [
            (r"\b(UPI|PAYTM|RAZORPAY)\b", "Bills", "DigitalPayment", "keyword:payment"),
            (r"\b(SWIGGY|ZOMATO|RESTAURANT|FOOD)\b", "Food", "Dining", "keyword:food"),
            (r"\b(UBER|OLA|TAXI|METRO|TRAVEL)\b", "Travel", "Transport", "keyword:travel"),
            (r"\b(NETFLIX|SPOTIFY|AUTOPAY|SUBSCRIPTION)\b", "Bills", "Subscription", "keyword:subscription"),
        ]

    def find_known_merchant(self, description: str) -> str | None:
        upper = description.upper()
        for merchant in self.merchant_map:
            if merchant in upper:
                return merchant
        return None

    def resolve_merchant_key(self, description: str) -> str:
        known = self.find_known_merchant(description)
        if known:
            return known.lower()
        cleaned = re.sub(r"[^A-Za-z\s]", " ", description.upper())
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if not cleaned:
            return ""
        tokens = []
        for token in cleaned.split(" "):
            if not token:
                continue
            if token.isdigit():
                continue
            if token in self.GENERIC_TOKENS:
                continue
            if token.startswith("ORDER"):
                continue
            tokens.append(token)
        if not tokens:
            return ""
        return tokens[0].lower()

    @staticmethod
    def _is_valid_merchant_key(merchant_key: str) -> bool:
        return bool(merchant_key and len(merchant_key) >= 3 and merchant_key.isalpha())

    def _categorize_deterministic(self, *, user_id: str, description: str, user_category: str | None = None) -> CategorizationResult:
        merchant_key = self.resolve_merchant_key(description)
        learned = self.overrides.get(user_id, merchant_key) if self._is_valid_merchant_key(merchant_key) else None
        if learned:
            return CategorizationResult(learned, "UserLearned", 0.99, "learned_override", "override:merchant", "User override learned")
        if user_category:
            if self._is_valid_merchant_key(merchant_key):
                self.overrides.set(user_id, merchant_key, user_category)
            return CategorizationResult(user_category, "UserProvided", 0.99, "user_provided", "request:category", "Category provided by user")
        known_merchant = self.find_known_merchant(description)
        if known_merchant:
            cat, subcat = self.merchant_map[known_merchant]
            return CategorizationResult(cat, subcat, 0.95, "merchant_mapping", f"merchant:{known_merchant}", "Matched known merchant")
        upper = description.upper()
        for pattern, cat, subcat, rule in self.keyword_rules:
            if re.search(pattern, upper):
                return CategorizationResult(cat, subcat, 0.85, "keyword_rule", rule, "Matched categorization rule")
        return CategorizationResult("Uncategorized", "General", 0.3, "fallback", "fallback:uncategorized", "No deterministic match")

    async def categorize_async(self, *, user_id: str, description: str, user_category: str | None = None) -> CategorizationResult:
        deterministic = self._categorize_deterministic(user_id=user_id, description=description, user_category=user_category)
        if deterministic.category != "Uncategorized" and deterministic.confidence >= 0.5:
            return deterministic
        if not self.ai.enabled or not self.ai.api_key:
            return deterministic
        ai_result = await self.ai.categorize(description)
        if ai_result:
            return ai_result
        return deterministic

    async def categorize(self, *, user_id: str, description: str, user_category: str | None = None) -> CategorizationResult:
        return await self.categorize_async(user_id=user_id, description=description, user_category=user_category)

    def categorize_sync(self, *, user_id: str, description: str, user_category: str | None = None) -> CategorizationResult:
        return self._categorize_deterministic(user_id=user_id, description=description, user_category=user_category)
