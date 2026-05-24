from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha1
from typing import Any

from app.models.schemas import GuidanceItem, GuidanceResponse
from app.services.guidance_policy import GuidancePolicy


class GuidanceEngine:
    def __init__(self, policy: GuidancePolicy | None = None) -> None:
        self.policy = policy or GuidancePolicy()

    def generate_guidance(
        self,
        *,
        transactions: list[dict[str, Any]],
        risk_result: dict[str, Any] | None,
        behavior_result: dict[str, Any] | None,
        score_result: dict[str, Any] | None,
    ) -> GuidanceResponse:
        risk_result = risk_result or {}
        behavior_result = behavior_result or {}
        score_result = score_result or {}
        now = datetime.now(UTC).isoformat()
        items: list[GuidanceItem] = []

        risk_events = risk_result.get("risk_events") or []
        for event in risk_events:
            evt_type = str(event.get("event_type") or "")
            if evt_type in {"cashflow_instability", "income_expense_imbalance"}:
                items.append(
                    self._item(
                        now=now,
                        gtype="CashflowStability",
                        priority="Critical" if evt_type == "income_expense_imbalance" else "High",
                        confidence=float(event.get("confidence") or 0.8),
                        title="Stabilize Monthly Cashflow",
                        rationale="Cashflow signals indicate expenses are pressuring your monthly balance.",
                        action_steps=[
                            "Freeze non-essential discretionary spending for 7 days.",
                            "Create a fixed cap for food, shopping, and travel categories this week.",
                            "Prioritize mandatory bills before any optional purchases.",
                        ],
                        expected_impact="Reduces short-term cash pressure and lowers overspend risk.",
                        source_signals=list(event.get("source_signals") or ["risk"]),
                        related=[str(event.get("risk_event_id") or "risk-event")],
                    )
                )
            if evt_type == "spending_velocity_spike":
                items.append(
                    self._item(
                        now=now,
                        gtype="SpendingVelocityControl",
                        priority="High",
                        confidence=float(event.get("confidence") or 0.78),
                        title="Slow Down Spending Velocity",
                        rationale="Recent spending is accelerating compared to your baseline trend.",
                        action_steps=[
                            "Limit discretionary shopping for the next 7 days.",
                            "Set a daily spending cap and track against it every evening.",
                            "Delay non-urgent purchases by 48 hours.",
                        ],
                        expected_impact="Improves spending stability and reduces anomaly pressure.",
                        source_signals=list(event.get("source_signals") or ["behavior"]),
                        related=[str(event.get("risk_event_id") or "risk-event")],
                    )
                )
            if evt_type == "category_drift":
                items.append(
                    self._item(
                        now=now,
                        gtype="BudgetOptimization",
                        priority="High",
                        confidence=float(event.get("confidence") or 0.8),
                        title="Rebalance Category Budgets",
                        rationale="Category drift indicates one or more spend buckets are above normal levels.",
                        action_steps=[
                            "Identify top two categories driving drift and set weekly limits.",
                            "Review merchant-level transactions in drifted categories.",
                            "Shift flexible expenses into next month where possible.",
                        ],
                        expected_impact="Brings category mix back toward a healthier baseline.",
                        source_signals=list(event.get("source_signals") or ["behavior"]),
                        related=[str(event.get("risk_event_id") or "risk-event")],
                    )
                )
                items.append(
                    self._item(
                        now=now,
                        gtype="MerchantHabitCorrection",
                        priority="Medium",
                        confidence=float(event.get("confidence") or 0.74),
                        title="Correct Merchant-Level Spending Habits",
                        rationale="Repeated merchant choices are reinforcing high-drift categories.",
                        action_steps=[
                            "List top merchants contributing to drift this month.",
                            "Replace at least one high-cost merchant with a lower-cost alternative.",
                            "Set a transaction limit per merchant for discretionary categories.",
                        ],
                        expected_impact="Reduces habitual overspending at high-impact merchants.",
                        source_signals=list(event.get("source_signals") or ["behavior"]),
                        related=[str(event.get("risk_event_id") or "risk-event")],
                    )
                )
            if evt_type == "recurring_burden":
                items.append(
                    self._item(
                        now=now,
                        gtype="SubscriptionOptimization",
                        priority="Medium",
                        confidence=float(event.get("confidence") or 0.72),
                        title="Optimize Recurring Commitments",
                        rationale="Recurring payment burden appears elevated relative to your current cashflow.",
                        action_steps=[
                            "Audit all subscriptions and recurring debits this week.",
                            "Cancel or downgrade at least one low-value recurring plan.",
                            "Move annual renewals to reminder mode before next billing cycle.",
                        ],
                        expected_impact="Lowers fixed outflow burden and improves monthly flexibility.",
                        source_signals=list(event.get("source_signals") or ["risk"]),
                        related=[str(event.get("risk_event_id") or "risk-event")],
                    )
                )
            if evt_type in {"low_financial_health_score", "high_value_spend"}:
                items.append(
                    self._item(
                        now=now,
                        gtype="RiskReduction",
                        priority="High",
                        confidence=float(event.get("confidence") or 0.8),
                        title="Reduce Immediate Financial Risk",
                        rationale="Current risk indicators suggest your spending pattern needs short-term correction.",
                        action_steps=[
                            "Avoid additional high-value purchases until weekly cashflow stabilizes.",
                            "Direct any surplus this week toward essential buffers or debt.",
                            "Re-check category limits daily for one week.",
                        ],
                        expected_impact="Lowers near-term risk intensity and improves financial resilience.",
                        source_signals=list(event.get("source_signals") or ["risk"]),
                        related=[str(event.get("risk_event_id") or "risk-event")],
                    )
                )
            items.append(
                self._item(
                    now=now,
                    gtype="RiskEventAction",
                    priority="High" if str(event.get("severity") or "") in {"High", "Critical"} else "Medium",
                    confidence=float(event.get("confidence") or 0.75),
                    title=f"Act On Risk Event: {evt_type.replace('_', ' ').title()}",
                    rationale=str(event.get("recommendation") or "A deterministic risk event needs corrective action."),
                    action_steps=[
                        "Review the evidence attached to this risk event.",
                        "Apply the suggested corrective action in the next 24 hours.",
                        "Re-check behavior and risk metrics after applying the change.",
                    ],
                    expected_impact="Targets a concrete risk signal with immediate corrective action.",
                    source_signals=list(event.get("source_signals") or ["risk"]),
                    related=[str(event.get("risk_event_id") or "risk-event")],
                )
            )

        if float(behavior_result.get("weekend_spending_drift") or 0) > self.policy.thresholds["weekend_spending_drift"]:
            items.append(
                self._item(
                    now=now,
                    gtype="WeekendSpendingControl",
                    priority="High",
                    confidence=0.85,
                    title="Control Weekend Spend Drift",
                    rationale="Weekend spending is materially higher than your weekday pattern.",
                    action_steps=[
                        "Set a fixed weekend discretionary budget before Friday.",
                        "Use one checkout pause rule before any non-essential spend.",
                        "Review weekend spend totals Sunday night.",
                    ],
                    expected_impact="Reduces weekend-driven budget slippage.",
                    source_signals=["behavior.weekend_spending_drift"],
                    related=[],
                )
            )

        if float(behavior_result.get("spend_velocity_7d_vs_30d") or 0) > self.policy.thresholds["velocity_spike"]:
            items.append(
                self._item(
                    now=now,
                    gtype="SpendingVelocityControl",
                    priority="Medium",
                    confidence=0.78,
                    title="Moderate Weekly Spend Acceleration",
                    rationale="7-day spend pace is above your recent 30-day baseline.",
                    action_steps=[
                        "Cap discretionary spending per day this week.",
                        "Delay any non-essential cart for 48 hours.",
                    ],
                    expected_impact="Smooths spend velocity and prevents anomaly escalation.",
                    source_signals=["behavior.spend_velocity_7d_vs_30d"],
                    related=[],
                )
            )

        score_metrics = score_result.get("metrics", {})
        has_savings_ratio = isinstance(score_metrics, dict) and "savings_ratio" in score_metrics
        savings_ratio = float(score_metrics.get("savings_ratio") or 0) if has_savings_ratio else None
        if savings_ratio is not None and savings_ratio < self.policy.thresholds["savings_ratio_low"]:
            items.append(
                self._item(
                    now=now,
                    gtype="SavingsImprovement",
                    priority="High",
                    confidence=0.89,
                    title="Improve Savings Ratio",
                    rationale="Savings ratio is below your healthy target band.",
                    action_steps=[
                        "Auto-transfer a fixed amount to savings right after income credit.",
                        "Reduce one discretionary category by 10-15% this month.",
                        "Track weekly savings progress every Monday.",
                    ],
                    expected_impact="Improves savings resilience and lowers risk pressure over time.",
                    source_signals=["scoring.metrics.savings_ratio"],
                    related=[],
                )
            )

        transaction_count = int(behavior_result.get("transaction_count") or len(transactions))
        if 0 < transaction_count < int(self.policy.thresholds["sparse_transactions"]):
            items.append(
                self._item(
                    now=now,
                    gtype="BudgetOptimization",
                    priority="Low",
                    confidence=0.7,
                    title="Upload More History For Stronger Guidance",
                    rationale="Current transaction history is limited, reducing confidence in trend guidance.",
                    action_steps=[
                        "Upload at least one additional month of transactions.",
                        "Ensure major recurring bills and income entries are present.",
                    ],
                    expected_impact="Improves personalization and guidance accuracy.",
                    source_signals=["behavior.transaction_count"],
                    related=[],
                )
            )

        if not items:
            items.append(
                self._item(
                    now=now,
                    gtype="PositiveReinforcement",
                    priority="Positive",
                    confidence=0.8,
                    title="Keep Up Stable Financial Habits",
                    rationale="No elevated deterministic behavior or risk concerns were detected.",
                    action_steps=[
                        "Continue current spending discipline this week.",
                        "Review budget categories once before month-end.",
                    ],
                    expected_impact="Maintains stability while preserving healthy financial momentum.",
                    source_signals=["score", "behavior", "risk"],
                    related=[],
                )
            )

        merged = self._merge_items(items)
        ranked = self._rank_items(merged)
        top_priority = ranked[0].priority if ranked else "Low"
        summary = self._summary(ranked)
        response = GuidanceResponse(
            generated_at=now,
            items=ranked,
            top_priority=top_priority,
            summary=summary,
            engine_version=self.policy.engine_version,
            guidance_items=ranked,
        )
        return response

    def build(self, risk: dict[str, Any], behavior: dict[str, Any], score: dict[str, Any]) -> dict[str, Any]:
        response = self.generate_guidance(
            transactions=[],
            risk_result=risk,
            behavior_result=behavior,
            score_result=score,
        )
        return response.model_dump()

    def _item(
        self,
        *,
        now: str,
        gtype: str,
        priority: str,
        confidence: float,
        title: str,
        rationale: str,
        action_steps: list[str],
        expected_impact: str,
        source_signals: list[str],
        related: list[str],
    ) -> GuidanceItem:
        cid = f"{gtype}:{title.strip().lower()}"
        guidance_id = f"guid_{sha1(cid.encode('utf-8')).hexdigest()[:12]}"
        actionability = self.policy.actionability_by_type.get(gtype, 0.72)
        ttl_days = self.policy.ttl_by_type.get(gtype, 7)
        return GuidanceItem(
            guidance_id=guidance_id,
            guidance_type=gtype,
            priority=priority,
            confidence=max(0.0, min(1.0, float(confidence))),
            actionability_score=max(0.0, min(1.0, float(actionability))),
            title=title,
            rationale=rationale,
            action_steps=action_steps[:4],
            expected_impact=expected_impact,
            source_signals=sorted(set(source_signals)),
            related_risk_events=sorted(set(related)),
            ttl_days=ttl_days,
            created_at=now,
            ttl_seconds=ttl_days * 86400,
            risk_event_ids=sorted(set(related)),
        )

    def _merge_items(self, items: list[GuidanceItem]) -> list[GuidanceItem]:
        merged: dict[str, GuidanceItem] = {}
        for item in items:
            key = f"{item.guidance_type}:{item.title.strip().lower()}"
            if key not in merged:
                merged[key] = item
                continue
            current = merged[key]
            better_priority = item if self._priority_weight(item.priority) > self._priority_weight(current.priority) else current
            merged_signals = sorted(set(current.source_signals + item.source_signals))
            merged_related = sorted(set(current.related_risk_events + item.related_risk_events))
            merged_steps = []
            for step in current.action_steps + item.action_steps:
                if step not in merged_steps:
                    merged_steps.append(step)
            merged[key] = GuidanceItem(
                guidance_id=current.guidance_id,
                guidance_type=current.guidance_type,
                priority=better_priority.priority,
                confidence=max(current.confidence, item.confidence),
                actionability_score=max(current.actionability_score, item.actionability_score),
                title=current.title,
                rationale=current.rationale if len(current.rationale) >= len(item.rationale) else item.rationale,
                action_steps=merged_steps[:4],
                expected_impact=current.expected_impact if len(current.expected_impact) >= len(item.expected_impact) else item.expected_impact,
                source_signals=merged_signals,
                related_risk_events=merged_related,
                ttl_days=min(current.ttl_days, item.ttl_days),
                created_at=current.created_at,
                ttl_seconds=min(current.ttl_seconds, item.ttl_seconds),
                risk_event_ids=merged_related,
            )
        return list(merged.values())

    def _rank_items(self, items: list[GuidanceItem]) -> list[GuidanceItem]:
        return sorted(
            items,
            key=lambda x: (
                -self._priority_weight(x.priority),
                -x.confidence,
                -x.actionability_score,
                -len(x.source_signals),
            ),
        )

    def _priority_weight(self, priority: str) -> float:
        return self.policy.priority_weights.get(priority, 0.0)

    @staticmethod
    def _summary(items: list[GuidanceItem]) -> str:
        if not items:
            return "No guidance items were generated."
        critical = sum(1 for i in items if i.priority == "Critical")
        high = sum(1 for i in items if i.priority == "High")
        return f"Generated {len(items)} guidance items ({critical} critical, {high} high priority)."
