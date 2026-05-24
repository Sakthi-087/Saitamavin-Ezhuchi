from __future__ import annotations

from typing import Any

from app.models.schemas import BehavioralIntelligenceResult
from app.services.behavioral_intelligence import BehavioralIntelligenceEngine


class BehaviorAnalysisService:
    def __init__(self) -> None:
        self.engine = BehavioralIntelligenceEngine()

    def analyze_behavior(self, transactions: list[dict[str, Any]]) -> BehavioralIntelligenceResult:
        return self.engine.analyze_behavior(transactions)
