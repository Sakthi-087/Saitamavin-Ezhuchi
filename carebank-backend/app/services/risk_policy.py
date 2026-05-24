from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RiskPolicy:
    engine_version: str = "risk-engine-v1"
    severity_weights: dict[str, float] = field(
        default_factory=lambda: {
            "Low": 15.0,
            "Moderate": 30.0,
            "High": 55.0,
            "Critical": 80.0,
        }
    )
    thresholds: dict[str, float] = field(
        default_factory=lambda: {
            "cashflow_instability_expense_ratio": 0.9,
            "velocity_spike": 0.35,
            "drift_high": 45.0,
            "drift_critical": 70.0,
            "anomaly_surge": 0.65,
            "high_value_spend": 2000.0,
            "income_expense_imbalance": 1.0,
            "low_financial_health_score": 45.0,
            "recurring_burden_count": 3.0,
            "recurring_burden_confidence": 0.7,
        }
    )
    confidence_rules: dict[str, float] = field(
        default_factory=lambda: {
            "base": 0.45,
            "event_weight": 0.45,
            "data_quality_weight": 0.1,
            "availability_bonus": 0.05,
        }
    )
    risk_score_caps: dict[str, float] = field(
        default_factory=lambda: {
            "min": 0.0,
            "max": 100.0,
        }
    )
