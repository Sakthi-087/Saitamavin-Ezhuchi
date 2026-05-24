from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class CopilotPolicy:
    supported_intents: list[str] = field(
        default_factory=lambda: [
            "financial_health_query",
            "risk_explanation",
            "guidance_explanation",
            "spending_summary",
            "behavior_drift_explanation",
            "simulation_explanation",
            "unsupported_investment_advice",
            "unsupported_legal_or_tax_advice",
            "prompt_injection_attempt",
            "general_financial_question",
        ]
    )
    blocked_patterns: list[re.Pattern[str]] = field(
        default_factory=lambda: [
            re.compile(r"\bignore previous instructions?\b", re.IGNORECASE),
            re.compile(r"\breveal system prompt\b", re.IGNORECASE),
            re.compile(r"\bshow hidden prompt\b", re.IGNORECASE),
            re.compile(r"\bbypass rules?\b", re.IGNORECASE),
            re.compile(r"\bdeveloper message\b", re.IGNORECASE),
            re.compile(r"\bsystem message\b", re.IGNORECASE),
            re.compile(r"\bprint your instructions?\b", re.IGNORECASE),
            re.compile(r"\bdisable safety\b", re.IGNORECASE),
            re.compile(r"\bact as unrestricted\b", re.IGNORECASE),
        ]
    )

    def classify_intent(self, message: str) -> str:
        text = (message or "").strip().lower()
        if any(pattern.search(text) for pattern in self.blocked_patterns):
            return "prompt_injection_attempt"
        if any(word in text for word in ("stock", "invest", "portfolio", "mutual fund", "crypto", "option trade")):
            return "unsupported_investment_advice"
        if any(word in text for word in ("tax", "legal", "lawsuit", "compliance filing", "itr")):
            return "unsupported_legal_or_tax_advice"
        if "simulation" in text or "what if" in text or "future balance" in text:
            return "simulation_explanation"
        if "drift" in text or "anomaly" in text or "behavior" in text:
            return "behavior_drift_explanation"
        if "guidance" in text or "recommendation" in text or "action step" in text:
            return "guidance_explanation"
        if "spending" in text or "expense" in text or "category total" in text:
            return "spending_summary"
        if "risk" in text or "unsafe" in text or "danger" in text:
            return "risk_explanation"
        if any(word in text for word in ("score", "health", "financial health", "status", "confidence")):
            return "financial_health_query"
        return "general_financial_question"

