from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha1
from typing import Any

from app.models.schemas import RiskEvent, RiskIntelligenceResult
from app.services.risk_policy import RiskPolicy


class RiskIntelligenceEngine:
    def __init__(self, policy: RiskPolicy | None = None) -> None:
        self.policy = policy or RiskPolicy()

    def analyze_risk(
        self,
        *,
        transactions: list[dict[str, Any]],
        behavior: dict[str, Any] | None,
        scoring: dict[str, Any] | None,
    ) -> RiskIntelligenceResult:
        now = datetime.now(UTC).isoformat()
        behavior = behavior or {}
        scoring = scoring or {}
        events: list[RiskEvent] = []

        income, expenses = self._extract_income_expenses(scoring)
        drift = self._normalize_drift(behavior.get("drift_score", 0))
        anomaly = self._clamp_0_1(behavior.get("anomaly_score", 0))
        velocity = abs(float(behavior.get("spend_velocity_7d_vs_30d") or behavior.get("spending_velocity") or 0.0))
        health_score = float(scoring.get("score") or 0.0)
        recurring = behavior.get("merchant_recurrence") or []

        expense_ratio = expenses / income if income > 0 else (1.2 if expenses > 0 else 0.0)
        if expense_ratio >= self.policy.thresholds["cashflow_instability_expense_ratio"]:
            events.append(
                self._event(
                    now=now,
                    event_type="cashflow_instability",
                    risk_type="cashflow",
                    severity="High" if expense_ratio > 1.0 else "Moderate",
                    confidence=self._clamp_0_1(0.55 + min(0.4, expense_ratio / 2.0)),
                    evidence={"expense_ratio": round(expense_ratio, 4), "income": income, "expenses": expenses},
                    recommendation="Reduce discretionary outflows and prioritize fixed obligations.",
                    source_signals=["scoring.metrics.income", "scoring.metrics.expenses"],
                )
            )

        if velocity >= self.policy.thresholds["velocity_spike"]:
            events.append(
                self._event(
                    now=now,
                    event_type="spending_velocity_spike",
                    risk_type="behavior",
                    severity="High" if velocity > 0.8 else "Moderate",
                    confidence=self._clamp_0_1(0.5 + min(0.45, velocity / 1.5)),
                    evidence={"spend_velocity_7d_vs_30d": round(velocity, 4)},
                    recommendation="Introduce short-term spend controls for the next 7-14 days.",
                    source_signals=["behavior.spend_velocity_7d_vs_30d"],
                )
            )

        if drift >= self.policy.thresholds["drift_high"]:
            events.append(
                self._event(
                    now=now,
                    event_type="category_drift",
                    risk_type="behavior",
                    severity="Critical" if drift >= self.policy.thresholds["drift_critical"] else "High",
                    confidence=self._clamp_0_1(0.55 + min(0.4, drift / 150.0)),
                    evidence={"drift_score": round(drift, 2), "drift_severity": behavior.get("drift_severity", "Unknown")},
                    recommendation="Review category-level budget drift and reset monthly limits.",
                    source_signals=["behavior.drift_score", "behavior.drift_severity"],
                )
            )

        if anomaly >= self.policy.thresholds["anomaly_surge"]:
            events.append(
                self._event(
                    now=now,
                    event_type="anomaly_surge",
                    risk_type="behavior",
                    severity="High",
                    confidence=self._clamp_0_1(0.55 + anomaly * 0.35),
                    evidence={"anomaly_score": round(anomaly, 4), "anomaly_count": int(behavior.get("metrics", {}).get("anomaly_count", 0))},
                    recommendation="Investigate unusual transaction patterns and pause non-essential spends.",
                    source_signals=["behavior.anomaly_score", "behavior.metrics.anomaly_count"],
                )
            )

        max_spend = self._max_expense_amount(transactions)
        if max_spend >= self.policy.thresholds["high_value_spend"]:
            events.append(
                self._event(
                    now=now,
                    event_type="high_value_spend",
                    risk_type="transaction",
                    severity="High",
                    confidence=0.9,
                    evidence={"max_transaction_amount": round(max_spend, 2), "threshold": self.policy.thresholds["high_value_spend"]},
                    recommendation="Validate high-value transactions and split large spends where possible.",
                    source_signals=["transactions.amount"],
                )
            )

        if income > 0 and (expenses / income) >= self.policy.thresholds["income_expense_imbalance"]:
            events.append(
                self._event(
                    now=now,
                    event_type="income_expense_imbalance",
                    risk_type="cashflow",
                    severity="Critical",
                    confidence=self._clamp_0_1(0.7 + min(0.25, (expenses / income) - 1.0)),
                    evidence={"income": income, "expenses": expenses, "expense_ratio": round(expenses / income, 4)},
                    recommendation="Reduce variable expenses immediately to restore positive monthly balance.",
                    source_signals=["scoring.metrics.income", "scoring.metrics.expenses"],
                )
            )

        if health_score and health_score <= self.policy.thresholds["low_financial_health_score"]:
            events.append(
                self._event(
                    now=now,
                    event_type="low_financial_health_score",
                    risk_type="scoring",
                    severity="High",
                    confidence=0.82,
                    evidence={"financial_health_score": health_score},
                    recommendation="Focus on savings and expense stability to improve financial health score.",
                    source_signals=["financial_health.score"],
                )
            )

        recurring_burden = [r for r in recurring if float(r.get("recurrence_confidence") or 0) >= self.policy.thresholds["recurring_burden_confidence"]]
        if len(recurring_burden) >= int(self.policy.thresholds["recurring_burden_count"]):
            events.append(
                self._event(
                    now=now,
                    event_type="recurring_burden",
                    risk_type="behavior",
                    severity="Moderate",
                    confidence=0.72,
                    evidence={"recurring_merchants": len(recurring_burden)},
                    recommendation="Audit recurring commitments and cancel low-value subscriptions.",
                    source_signals=["behavior.merchant_recurrence"],
                )
            )

        overall_score = self._overall_score(events)
        risk_level = self._risk_level(overall_score)
        confidence = self._overall_confidence(events, behavior=behavior, scoring=scoring, transactions=transactions)
        risk_signals = sorted({signal for event in events for signal in event.source_signals})
        evidence_summary = self._evidence_summary(events)
        recommendation_text = self._recommendation_text(events)

        return RiskIntelligenceResult(
            overall_risk_score=overall_score,
            risk_level=risk_level,
            confidence=confidence,
            risk_events=events,
            risk_signals=risk_signals,
            evidence_summary=evidence_summary,
            recommendation_text=recommendation_text,
            generated_at=now,
            engine_version=self.policy.engine_version,
        )

    def analyze(self, behavior: dict[str, Any], scoring: dict[str, Any]) -> dict[str, Any]:
        result = self.analyze_risk(transactions=[], behavior=behavior, scoring=scoring)
        drift_raw = self._normalize_drift(behavior.get("drift_score", 0))
        drift_norm = drift_raw / 100.0
        anomaly = self._clamp_0_1(behavior.get("anomaly_score", 0))
        risk_component = float(scoring.get("breakdown", {}).get("risk_score") or 0.0)
        legacy_severity = "Low"
        if risk_component < 40 or drift_norm > 0.7 or anomaly > 0.7:
            legacy_severity = "High"
        elif risk_component < 65 or drift_norm > 0.4 or anomaly > 0.4:
            legacy_severity = "Medium"
        return {
            "severity": legacy_severity,
            "confidence": result.confidence,
            "rationale": result.evidence_summary,
            "evidence": {
                "overall_risk_score": result.overall_risk_score,
                "risk_level": result.risk_level,
                "risk_event_count": len(result.risk_events),
                "top_events": [event.event_type for event in result.risk_events[:3]],
            },
            "source_signals": result.risk_signals,
            "mitigation_suggestion": result.recommendation_text,
            "risk_events": [event.model_dump() for event in result.risk_events],
            "overall_risk_score": result.overall_risk_score,
            "risk_level": result.risk_level,
            "overall_risk_level": result.risk_level,
            "evidence_summary": result.evidence_summary,
            "recommendation_text": result.recommendation_text,
            "generated_at": result.generated_at,
            "engine_version": result.engine_version,
            "risk_graph": {
                "nodes": ["behavior", "transactions", "scoring", "risk_events", "risk_result"],
                "edges": [["behavior", "risk_events"], ["transactions", "risk_events"], ["scoring", "risk_events"], ["risk_events", "risk_result"]],
            },
        }

    def _extract_income_expenses(self, scoring: dict[str, Any]) -> tuple[float, float]:
        metrics = scoring.get("metrics", {})
        income = float(metrics.get("income") or 0.0)
        expenses = float(metrics.get("expenses") or 0.0)
        return max(0.0, income), max(0.0, expenses)

    def _overall_score(self, events: list[RiskEvent]) -> float:
        score = 0.0
        for event in events:
            weight = self.policy.severity_weights.get(event.severity, 15.0)
            score += weight * event.confidence * 0.18
        return round(max(self.policy.risk_score_caps["min"], min(self.policy.risk_score_caps["max"], score)), 2)

    def _overall_confidence(
        self,
        events: list[RiskEvent],
        *,
        behavior: dict[str, Any],
        scoring: dict[str, Any],
        transactions: list[dict[str, Any]],
    ) -> float:
        base = self.policy.confidence_rules["base"]
        event_part = mean_conf = (sum(event.confidence for event in events) / len(events)) if events else 0.0
        parse_errors = len(behavior.get("parse_errors") or [])
        valid_count = int(behavior.get("valid_transaction_count") or len(transactions))
        quality = 1.0 if valid_count <= 0 else max(0.0, min(1.0, 1.0 - (parse_errors / valid_count)))
        avail = 0.0
        if behavior:
            avail += self.policy.confidence_rules["availability_bonus"]
        if scoring:
            avail += self.policy.confidence_rules["availability_bonus"]
        confidence = (
            base
            + mean_conf * self.policy.confidence_rules["event_weight"]
            + quality * self.policy.confidence_rules["data_quality_weight"]
            + avail
        )
        return round(self._clamp_0_1(confidence), 4)

    @staticmethod
    def _normalize_drift(value: Any) -> float:
        try:
            drift_raw = float(value or 0.0)
        except (TypeError, ValueError):
            drift_raw = 0.0
        drift_raw = max(0.0, drift_raw)
        return drift_raw if drift_raw > 1 else drift_raw * 100.0

    @staticmethod
    def _clamp_0_1(value: Any) -> float:
        try:
            v = float(value)
        except (TypeError, ValueError):
            v = 0.0
        return max(0.0, min(1.0, v))

    @staticmethod
    def _risk_level(score: float) -> str:
        if score <= 20:
            return "Low"
        if score <= 45:
            return "Moderate"
        if score <= 70:
            return "High"
        return "Critical"

    @staticmethod
    def _legacy_severity(level: str) -> str:
        if level in {"Critical", "High"}:
            return "High"
        if level == "Moderate":
            return "Medium"
        return "Low"

    @staticmethod
    def _max_expense_amount(transactions: list[dict[str, Any]]) -> float:
        max_amt = 0.0
        for tx in transactions:
            try:
                amount = abs(float(tx.get("amount") or 0.0))
            except (TypeError, ValueError):
                continue
            if amount > max_amt:
                max_amt = amount
        return max_amt

    def _event(
        self,
        *,
        now: str,
        event_type: str,
        risk_type: str,
        severity: str,
        confidence: float,
        evidence: dict[str, Any],
        recommendation: str,
        source_signals: list[str],
    ) -> RiskEvent:
        confidence = self._clamp_0_1(confidence)
        event_id_raw = f"{self.policy.engine_version}:{event_type}:{severity}:{sorted(source_signals)}:{sorted(evidence.keys())}"
        risk_event_id = f"risk_{sha1(event_id_raw.encode('utf-8')).hexdigest()[:12]}"
        return RiskEvent(
            risk_event_id=risk_event_id,
            event_type=event_type,
            risk_type=risk_type,
            severity=severity,
            confidence=confidence,
            evidence=evidence,
            recommendation=recommendation,
            source_signals=source_signals,
            created_at=now,
        )

    @staticmethod
    def _evidence_summary(events: list[RiskEvent]) -> str:
        if not events:
            return "No elevated deterministic risk events were detected."
        top = events[:3]
        labels = ", ".join(event.event_type for event in top)
        return f"Detected {len(events)} risk events led by: {labels}."

    @staticmethod
    def _recommendation_text(events: list[RiskEvent]) -> str:
        if not events:
            return "Maintain current spending discipline and monitor category drift weekly."
        return events[0].recommendation
