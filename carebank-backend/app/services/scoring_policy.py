from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ScoringPolicy:
    scoring_version: str = "carebank-score-v1.0"
    component_weights: dict[str, float] = field(
        default_factory=lambda: {
            "savings_score": 0.35,
            "stability_score": 0.20,
            "discipline_score": 0.20,
            "risk_score": 0.25,
        }
    )
    thresholds: dict[str, float] = field(
        default_factory=lambda: {
            "savings_excellent": 0.4,
            "savings_good": 0.2,
            "high_value_threshold": 2000.0,
            "impulse_threshold": 750.0,
            "sparse_tx_count": 5.0,
            "low_savings_ratio": 0.1,
            "high_risk_score": 70.0,
            "high_drift_score": 60.0,
            "high_anomaly_count": 3.0,
        }
    )
    penalty_caps: dict[str, float] = field(
        default_factory=lambda: {
            "high_risk_intelligence": 8.0,
            "high_behavior_drift": 6.0,
            "multiple_anomalies": 5.0,
            "cashflow_instability": 8.0,
            "negative_net_balance_trend": 4.0,
            "low_savings_ratio": 5.0,
            "sparse_data": 4.0,
            "no_income_data": 7.0,
        }
    )
    confidence_rules: dict[str, float] = field(
        default_factory=lambda: {
            "base_confidence": 0.55,
            "base_quality": 0.7,
            "sparse_penalty": 0.2,
            "no_income_penalty": 0.2,
            "parse_error_penalty_per_item": 0.05,
            "history_depth_bonus_cap": 0.2,
            "history_depth_days_for_max_bonus": 90.0,
        }
    )
    status_mapping: list[tuple[int, int, str]] = field(
        default_factory=lambda: [
            (80, 100, "Excellent"),
            (65, 79, "Good"),
            (45, 64, "Moderate"),
            (25, 44, "Weak"),
            (0, 24, "Critical"),
        ]
    )

    def validate_weights(self) -> None:
        total = sum(self.component_weights.values())
        if abs(total - 1.0) > 1e-9:
            raise ValueError(f"Scoring weights must sum to 1.0, found {total}")
