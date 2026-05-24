from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GuidancePolicy:
    engine_version: str = "guidance-engine-v1"
    priority_order: list[str] = field(default_factory=lambda: ["Critical", "High", "Medium", "Low", "Positive"])
    priority_weights: dict[str, float] = field(
        default_factory=lambda: {"Critical": 5.0, "High": 4.0, "Medium": 3.0, "Low": 2.0, "Positive": 1.0}
    )
    confidence_weights: dict[str, float] = field(default_factory=lambda: {"base": 0.6, "event_boost": 0.4})
    actionability_weights: dict[str, float] = field(default_factory=lambda: {"base": 0.5, "event_boost": 0.5})
    ttl_by_type: dict[str, int] = field(
        default_factory=lambda: {
            "RiskReduction": 3,
            "RiskEventAction": 3,
            "CashflowStability": 5,
            "BudgetOptimization": 7,
            "SpendingVelocityControl": 5,
            "WeekendSpendingControl": 7,
            "SavingsImprovement": 14,
            "SubscriptionOptimization": 14,
            "MerchantHabitCorrection": 10,
            "PositiveReinforcement": 14,
        }
    )
    actionability_by_type: dict[str, float] = field(
        default_factory=lambda: {
            "RiskReduction": 0.9,
            "RiskEventAction": 0.88,
            "CashflowStability": 0.86,
            "BudgetOptimization": 0.82,
            "SpendingVelocityControl": 0.84,
            "WeekendSpendingControl": 0.8,
            "SavingsImprovement": 0.78,
            "SubscriptionOptimization": 0.79,
            "MerchantHabitCorrection": 0.76,
            "PositiveReinforcement": 0.62,
        }
    )
    thresholds: dict[str, float] = field(
        default_factory=lambda: {
            "weekend_spending_drift": 0.5,
            "velocity_spike": 0.35,
            "savings_ratio_low": 0.2,
            "sparse_transactions": 8,
        }
    )
