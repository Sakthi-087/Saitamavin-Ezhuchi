from __future__ import annotations

from app.models.schemas import FinancialHealth, SpendingSummary, Transaction
from app.services.scoring import FinancialScoringEngine


class FinancialHealthAgent:
    def __init__(self) -> None:
        self.scoring_engine = FinancialScoringEngine()

    def analyze(self, transactions: list[Transaction], spending: SpendingSummary) -> FinancialHealth:
        score_result = self.scoring_engine.calculate(transactions)
        savings_rate = max(0.0, score_result.metrics.savings_ratio * 100.0)

        return FinancialHealth(
            score=round(score_result.score),
            status=score_result.status,
            risk_indicator=self.scoring_engine.get_risk_indicator(score_result.score),
            summary=score_result.summary,
            savings_rate=round(savings_rate, 2),
            breakdown=score_result.breakdown,
            metrics=score_result.metrics,
            scoring_version=score_result.scoring_version,
            explainability=score_result.explainability,
            confidence=score_result.confidence,
        )
