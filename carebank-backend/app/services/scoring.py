from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from statistics import pstdev
from typing import Any

from app.models.schemas import (
    FinancialScoreResponse,
    ScoreBreakdown,
    ScoreConfidence,
    ScoreContribution,
    ScoreExplainability,
    ScoreMetrics,
    ScorePenalty,
    Transaction,
)
from app.services.scoring_policy import ScoringPolicy
from app.services.transaction_utils import is_income_transaction, normalized_expense_amount


class FinancialScoringEngine:
    IMPULSE_CATEGORIES = {"shopping", "food", "travel"}

    def __init__(self, policy: ScoringPolicy | None = None) -> None:
        self.policy = policy or ScoringPolicy()
        self.policy.validate_weights()

    def calculate(
        self,
        transactions: list[Transaction],
        *,
        behavior_result: dict[str, Any] | None = None,
        risk_result: dict[str, Any] | None = None,
    ) -> FinancialScoreResponse:
        behavior_result = behavior_result or {}
        risk_result = risk_result or {}

        if not transactions:
            return self._empty_response()

        income, expenses, expense_transactions = self._split_transactions(transactions)
        savings_ratio = ((income - expenses) / income) if income > 0 else 0.0
        savings_score = self._score_savings_ratio(savings_ratio)

        daily_expense_totals = self._daily_expense_totals(expense_transactions)
        expense_volatility = pstdev(daily_expense_totals) if len(daily_expense_totals) > 1 else 0.0
        stability_score = self._score_stability(daily_expense_totals, expense_volatility)

        high_value_threshold = self.policy.thresholds["high_value_threshold"]
        impulse_threshold = self.policy.thresholds["impulse_threshold"]
        high_value_expense_count = sum(1 for transaction in expense_transactions if transaction.amount >= high_value_threshold)
        impulse_spend_count = sum(
            1
            for transaction in expense_transactions
            if transaction.amount >= impulse_threshold and transaction.category.lower() in self.IMPULSE_CATEGORIES
        )
        discipline_score = self._score_discipline(high_value_expense_count, impulse_spend_count)

        expense_ratio = (expenses / income) if income > 0 else 1.0
        net_balance_trend = self._net_balance_trend(transactions)
        risk_score = self._score_risk(expense_ratio, net_balance_trend, income, expenses)

        breakdown = ScoreBreakdown(
            savings_score=round(self._clamp_0_100(savings_score), 2),
            stability_score=round(self._clamp_0_100(stability_score), 2),
            discipline_score=round(self._clamp_0_100(discipline_score), 2),
            risk_score=round(self._clamp_0_100(risk_score), 2),
        )
        metrics = ScoreMetrics(
            savings_ratio=round(savings_ratio, 4),
            income=round(income, 2),
            expenses=round(expenses, 2),
            expense_volatility=round(expense_volatility, 2),
            high_value_expense_count=high_value_expense_count,
            impulse_spend_count=impulse_spend_count,
            expense_ratio=round(expense_ratio, 4) if income > 0 else 0.0,
            net_balance_trend=round(net_balance_trend, 2),
        )

        contributions = self._contributions(breakdown)
        weighted_score = sum(item.weighted_points for item in contributions)
        penalties = self._penalties(
            metrics=metrics,
            behavior_result=behavior_result,
            risk_result=risk_result,
            transaction_count=len(transactions),
            income=income,
        )
        total_penalty = sum(item.points_deducted for item in penalties)
        final_score = self._clamp_0_100(weighted_score - total_penalty)
        status = self.get_status(final_score)
        confidence = self._confidence(
            transactions=transactions,
            income=income,
            behavior_result=behavior_result,
        )

        source_summary = sorted(
            set(
                [signal for item in contributions for signal in item.source_signals]
                + [item.source_signal for item in penalties]
            )
        )
        explainability = ScoreExplainability(
            scoring_version=self.policy.scoring_version,
            contributions=contributions,
            penalties=penalties,
            final_score_formula="sum(component_raw_score * weight) - sum(penalties)",
            source_summary=source_summary,
        )

        major_issues = [p.reason for p in penalties[:3]]
        positive_signals = self._positive_signals(breakdown, metrics)
        risk_timeline = self._risk_timeline(transactions)
        return FinancialScoreResponse(
            score=round(final_score, 2),
            status=status,
            breakdown=breakdown,
            metrics=metrics,
            summary=self._build_summary(status, breakdown, metrics, confidence),
            major_issues=major_issues,
            positive_signals=positive_signals,
            risk_timeline=risk_timeline,
            scoring_version=self.policy.scoring_version,
            explainability=explainability,
            confidence=confidence,
        )

    def _empty_response(self) -> FinancialScoreResponse:
        breakdown = ScoreBreakdown(savings_score=0.0, stability_score=40.0, discipline_score=45.0, risk_score=20.0)
        metrics = ScoreMetrics(
            savings_ratio=0.0,
            income=0.0,
            expenses=0.0,
            expense_volatility=0.0,
            high_value_expense_count=0,
            impulse_spend_count=0,
            expense_ratio=0.0,
            net_balance_trend=0.0,
        )
        contributions = self._contributions(breakdown)
        penalties = [
            ScorePenalty(
                penalty_type="sparse_data",
                points_deducted=self.policy.penalty_caps["sparse_data"],
                reason="Limited transaction history; score may be less reliable.",
                source_signal="transactions.count",
                severity="Medium",
            ),
            ScorePenalty(
                penalty_type="no_income_data",
                points_deducted=self.policy.penalty_caps["no_income_data"],
                reason="No income data detected in available transactions.",
                source_signal="metrics.income",
                severity="High",
            ),
        ]
        final_score = self._clamp_0_100(sum(c.weighted_points for c in contributions) - sum(p.points_deducted for p in penalties))
        confidence = ScoreConfidence(
            confidence_score=0.2,
            data_quality_score=0.3,
            history_depth=0,
            transaction_count=0,
            valid_transaction_ratio=0.0,
            limitations=["Limited transaction history; score may be less reliable.", "No income data detected."],
        )
        explainability = ScoreExplainability(
            scoring_version=self.policy.scoring_version,
            contributions=contributions,
            penalties=penalties,
            final_score_formula="sum(component_raw_score * weight) - sum(penalties)",
            source_summary=["transactions.count", "metrics.income"],
        )
        return FinancialScoreResponse(
            score=round(final_score, 2),
            status=self.get_status(final_score),
            breakdown=breakdown,
            metrics=metrics,
            summary="Limited data was available, so this score is a conservative baseline.",
            major_issues=[p.reason for p in penalties],
            positive_signals=[],
            risk_timeline=[],
            scoring_version=self.policy.scoring_version,
            explainability=explainability,
            confidence=confidence,
        )

    def get_status(self, score: float) -> str:
        rounded = int(round(self._clamp_0_100(score)))
        for low, high, label in self.policy.status_mapping:
            if low <= rounded <= high:
                return label
        return "Critical"

    def get_risk_indicator(self, score: float) -> str:
        status = self.get_status(score)
        if status in {"Excellent", "Good"}:
            return "Low"
        if status == "Moderate":
            return "Medium"
        return "High"

    def _split_transactions(self, transactions: list[Transaction]) -> tuple[float, float, list[Transaction]]:
        income = 0.0
        expenses = 0.0
        expense_transactions: list[Transaction] = []
        for transaction in transactions:
            if is_income_transaction(transaction):
                income += normalized_expense_amount(transaction)
            else:
                expense_amount = normalized_expense_amount(transaction)
                expenses += expense_amount
                expense_transactions.append(
                    Transaction(
                        date=transaction.date,
                        description=transaction.description,
                        amount=expense_amount,
                        category=transaction.category,
                    )
                )
        return income, expenses, expense_transactions

    def _score_savings_ratio(self, savings_ratio: float) -> float:
        excellent = self.policy.thresholds["savings_excellent"]
        good = self.policy.thresholds["savings_good"]
        if savings_ratio >= excellent:
            return 100.0
        if savings_ratio >= good:
            return 60.0 + ((savings_ratio - good) / max(excellent - good, 1e-6)) * 40.0
        if savings_ratio > 0:
            return (savings_ratio / max(good, 1e-6)) * 60.0
        return 0.0

    def _daily_expense_totals(self, transactions: list[Transaction]) -> list[float]:
        grouped: dict[str, float] = defaultdict(float)
        for transaction in transactions:
            grouped[transaction.date] += transaction.amount
        return list(grouped.values())

    def _score_stability(self, daily_totals: list[float], expense_volatility: float) -> float:
        if len(daily_totals) <= 1:
            return 45.0
        average_daily_spend = sum(daily_totals) / len(daily_totals)
        if average_daily_spend <= 0:
            return 45.0
        variability_ratio = expense_volatility / average_daily_spend
        return 100.0 - variability_ratio * 100.0

    def _score_discipline(self, high_value_count: int, impulse_spend_count: int) -> float:
        penalty = high_value_count * 8.0 + max(0, impulse_spend_count - 2) * 4.0
        return 100.0 - penalty

    def _net_balance_trend(self, transactions: list[Transaction]) -> float:
        monthly_net: dict[str, float] = defaultdict(float)
        for transaction in transactions:
            month = transaction.date[:7]
            if is_income_transaction(transaction):
                monthly_net[month] += normalized_expense_amount(transaction)
            else:
                monthly_net[month] -= normalized_expense_amount(transaction)
        months = sorted(monthly_net)
        if len(months) < 2:
            return 0.0
        return monthly_net[months[-1]] - monthly_net[months[-2]]

    def _score_risk(self, expense_ratio: float, net_balance_trend: float, income: float, expenses: float) -> float:
        if income <= 0:
            return 20.0
        base_score = 100.0 - expense_ratio * 100.0
        if expenses > income:
            base_score -= 20.0
        if net_balance_trend < 0:
            base_score -= min(20.0, abs(net_balance_trend) / max(income, 1.0) * 100.0)
        return base_score

    def _contributions(self, breakdown: ScoreBreakdown) -> list[ScoreContribution]:
        defs = [
            ("savings_score", breakdown.savings_score, "Savings capacity from income-expense spread.", ["metrics.savings_ratio"]),
            ("stability_score", breakdown.stability_score, "Day-to-day expense volatility stability.", ["metrics.expense_volatility"]),
            ("discipline_score", breakdown.discipline_score, "Impulse and high-value spend discipline.", ["metrics.high_value_expense_count", "metrics.impulse_spend_count"]),
            ("risk_score", breakdown.risk_score, "Cashflow and balance risk posture.", ["metrics.expense_ratio", "metrics.net_balance_trend"]),
        ]
        out: list[ScoreContribution] = []
        for component, raw_score, explanation, source in defs:
            weight = self.policy.component_weights[component]
            out.append(
                ScoreContribution(
                    component=component,
                    raw_score=round(self._clamp_0_100(raw_score), 2),
                    weight=weight,
                    weighted_points=round(self._clamp_0_100(raw_score) * weight, 2),
                    explanation=explanation,
                    source_signals=source,
                )
            )
        return out

    def _penalties(
        self,
        *,
        metrics: ScoreMetrics,
        behavior_result: dict[str, Any],
        risk_result: dict[str, Any],
        transaction_count: int,
        income: float,
    ) -> list[ScorePenalty]:
        penalties: list[ScorePenalty] = []

        def add(ptype: str, points: float, reason: str, source: str, severity: str) -> None:
            cap = self.policy.penalty_caps[ptype]
            penalties.append(
                ScorePenalty(
                    penalty_type=ptype,
                    points_deducted=round(min(cap, max(0.0, points)), 2),
                    reason=reason,
                    source_signal=source,
                    severity=severity,
                )
            )

        risk_score = float(risk_result.get("overall_risk_score") or 0.0)
        if risk_score >= self.policy.thresholds["high_risk_score"]:
            add("high_risk_intelligence", risk_score / 20.0, "Risk intelligence score is elevated.", "risk.overall_risk_score", "High")

        drift_raw = float(behavior_result.get("drift_score") or 0.0)
        drift = drift_raw if drift_raw > 1 else drift_raw * 100.0
        if drift >= self.policy.thresholds["high_drift_score"]:
            add("high_behavior_drift", drift / 25.0, "Behavior drift is materially above baseline.", "behavior.drift_score", "High")

        anomaly_count = int(behavior_result.get("metrics", {}).get("anomaly_count") or len(behavior_result.get("anomaly_events") or []))
        if anomaly_count >= int(self.policy.thresholds["high_anomaly_count"]):
            add("multiple_anomalies", anomaly_count, "Multiple anomaly events detected.", "behavior.metrics.anomaly_count", "Medium")

        if any(str(evt.get("event_type") or "") == "cashflow_instability" for evt in risk_result.get("risk_events") or []):
            add("cashflow_instability", 6.0, "Cashflow instability risk event detected.", "risk.risk_events.cashflow_instability", "High")

        if metrics.net_balance_trend < 0:
            add("negative_net_balance_trend", abs(metrics.net_balance_trend) / max(metrics.income, 1.0) * 10.0, "Net balance trend is negative month-over-month.", "metrics.net_balance_trend", "Medium")

        if metrics.savings_ratio < self.policy.thresholds["low_savings_ratio"]:
            add("low_savings_ratio", (self.policy.thresholds["low_savings_ratio"] - metrics.savings_ratio) * 20.0, "Savings ratio is below healthy threshold.", "metrics.savings_ratio", "Medium")

        if transaction_count < int(self.policy.thresholds["sparse_tx_count"]):
            add("sparse_data", 3.0, "Limited transaction history; score may be less reliable.", "transactions.count", "Low")

        if income <= 0:
            add("no_income_data", 6.0, "No income data detected in available transactions.", "metrics.income", "High")
        return [p for p in penalties if p.points_deducted > 0]

    def _confidence(
        self,
        *,
        transactions: list[Transaction],
        income: float,
        behavior_result: dict[str, Any],
    ) -> ScoreConfidence:
        tx_count = len(transactions)
        parse_errors = len(behavior_result.get("parse_errors") or [])
        valid_ratio = 1.0 if tx_count == 0 else max(0.0, min(1.0, (tx_count - parse_errors) / max(tx_count, 1)))
        if tx_count >= 2:
            dates = sorted(self._parse_date_safe(t.date) for t in transactions if self._parse_date_safe(t.date) is not None)
            history_depth = max(0, (dates[-1] - dates[0]).days) if len(dates) >= 2 else 0
        else:
            history_depth = 0
        rules = self.policy.confidence_rules
        quality = rules["base_quality"] * valid_ratio
        quality -= parse_errors * rules["parse_error_penalty_per_item"]
        quality = max(0.0, min(1.0, quality))
        conf = rules["base_confidence"]
        limitations: list[str] = []
        if tx_count < int(self.policy.thresholds["sparse_tx_count"]):
            conf -= rules["sparse_penalty"]
            limitations.append("Limited transaction history; score may be less reliable.")
        if income <= 0:
            conf -= rules["no_income_penalty"]
            limitations.append("No income data detected in available transactions.")
        if parse_errors > 0:
            limitations.append("Some records were excluded due to data quality issues.")
        depth_bonus = min(
            rules["history_depth_bonus_cap"],
            (history_depth / max(rules["history_depth_days_for_max_bonus"], 1.0)) * rules["history_depth_bonus_cap"],
        )
        conf = max(0.0, min(1.0, conf + depth_bonus - (1.0 - quality) * 0.2))
        return ScoreConfidence(
            confidence_score=round(conf, 4),
            data_quality_score=round(quality, 4),
            history_depth=history_depth,
            transaction_count=tx_count,
            valid_transaction_ratio=round(valid_ratio, 4),
            limitations=limitations,
        )

    def _positive_signals(self, breakdown: ScoreBreakdown, metrics: ScoreMetrics) -> list[str]:
        out: list[str] = []
        if breakdown.savings_score >= 70:
            out.append("Savings behavior is healthy relative to income.")
        if breakdown.stability_score >= 65:
            out.append("Spending stability is improving with lower volatility.")
        if metrics.net_balance_trend >= 0:
            out.append("Net monthly balance trend is stable or improving.")
        return out

    def _risk_timeline(self, transactions: list[Transaction]) -> list[dict[str, Any]]:
        monthly: dict[str, dict[str, float]] = defaultdict(lambda: {"income": 0.0, "expenses": 0.0})
        for tx in transactions:
            month = tx.date[:7]
            amount = normalized_expense_amount(tx)
            if is_income_transaction(tx):
                monthly[month]["income"] += amount
            else:
                monthly[month]["expenses"] += amount
        out = []
        for month in sorted(monthly.keys()):
            income = monthly[month]["income"]
            expenses = monthly[month]["expenses"]
            ratio = (expenses / income) if income > 0 else 0.0
            out.append({"month": month, "expense_ratio": round(ratio, 4), "income": round(income, 2), "expenses": round(expenses, 2)})
        return out

    @staticmethod
    def _parse_date_safe(value: str) -> datetime | None:
        try:
            return datetime.fromisoformat(value[:10])
        except ValueError:
            return None

    @staticmethod
    def _clamp_0_100(value: float) -> float:
        return max(0.0, min(100.0, value))

    def _build_summary(
        self,
        status: str,
        breakdown: ScoreBreakdown,
        metrics: ScoreMetrics,
        confidence: ScoreConfidence,
    ) -> str:
        base = (
            f"Status is {status.lower()} with savings {breakdown.savings_score:.0f}/100, "
            f"stability {breakdown.stability_score:.0f}/100, discipline {breakdown.discipline_score:.0f}/100, "
            f"and risk {breakdown.risk_score:.0f}/100."
        )
        confidence_note = f" Confidence is {confidence.confidence_score:.2f} based on available history."
        return base + confidence_note
