from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.models.schemas import AnalysisResponse, KPIItem, Transaction
from app.services.advisory import AdvisoryAgent
from app.services.alerts import AlertAgent
from app.services.behavioral_intelligence import BehavioralIntelligenceEngine
from app.services.copilot_orchestrator import CopilotOrchestrator
from app.services.event_store import EventStore
from app.services.guidance_engine import GuidanceEngine
from app.services.health import FinancialHealthAgent
from app.services.llm import LLMService
from app.services.risk_intelligence import RiskIntelligenceEngine
from app.services.spending import SpendingAnalysisAgent
from pathlib import Path


class CoordinatorAgent:
    def __init__(self) -> None:
        self.spending_agent = SpendingAnalysisAgent()
        self.health_agent = FinancialHealthAgent()
        self.alert_agent = AlertAgent()
        self.advisory_agent = AdvisoryAgent()
        self.llm_service = LLMService()
        self.behavior_engine = BehavioralIntelligenceEngine()
        self.risk_engine = RiskIntelligenceEngine()
        self.guidance_engine = GuidanceEngine()
        self.copilot = CopilotOrchestrator()
        self.event_store = EventStore(Path(__file__).resolve().parents[2])

    async def analyze(self, transactions: list[Transaction]) -> AnalysisResponse:
        spending_context = self.spending_agent.analyze(transactions)
        spending = spending_context["summary"]
        health = self.health_agent.analyze(transactions, spending)
        tx_payload = [t.model_dump() for t in transactions]
        behavior = self.behavior_engine.analyze(tx_payload)
        risk_typed = self.risk_engine.analyze_risk(
            transactions=tx_payload,
            behavior=behavior,
            scoring=health.model_dump(),
        )
        risk = self.risk_engine.analyze(behavior, health.model_dump())
        risk["typed"] = risk_typed.model_dump()
        alerts = self.alert_agent.analyze(spending_context, health, risk)
        recommendations = self.advisory_agent.analyze(spending, alerts, health)
        guidance_typed = self.guidance_engine.generate_guidance(
            transactions=tx_payload,
            risk_result=risk,
            behavior_result=behavior,
            score_result=health.model_dump(),
        )
        guidance = guidance_typed.model_dump()

        insights = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "currency": "INR",
            "current_month": spending_context["current_month"],
            "previous_month": spending_context["previous_month"],
            "risk_indicator": health.risk_indicator,
            "transaction_count": len(transactions),
            "behavior": behavior,
            "risk_intelligence": risk,
            "guidance": guidance,
        }
        self.event_store.append("behavior", behavior)
        self.event_store.append("risk", risk)
        self.event_store.append("guidance", guidance)
        self.event_store.append("score", health.model_dump())

        structured_payload = {
            "financial_health": health.model_dump(),
            "spending": spending.model_dump(),
            "alerts": alerts,
            "recommendations": recommendations,
            "insights": insights,
        }
        explanation = await self.llm_service.generate_explanation(structured_payload)

        return AnalysisResponse(
            financial_health=health,
            spending=spending,
            alerts=alerts,
            recommendations=recommendations,
            ai_explanation=explanation,
            kpis=self._build_kpis(spending, health, alerts),
            chart_data=spending_context["chart_data"],
            insights=insights,
        )

    async def chat(self, message: str, transactions: list[Transaction]) -> dict[str, Any]:
        analysis = await self.analyze(transactions)
        structured_payload = analysis.model_dump()
        response = await self.copilot.respond(message, structured_payload)
        minimal_context = {
            "financial_health": {
                "score": structured_payload.get("financial_health", {}).get("score"),
                "status": structured_payload.get("financial_health", {}).get("status"),
            },
            "risk": {
                "overall_risk_score": structured_payload.get("insights", {}).get("risk_intelligence", {}).get("overall_risk_score"),
                "severity": structured_payload.get("insights", {}).get("risk_intelligence", {}).get("severity"),
            },
            "guidance_count": len((structured_payload.get("insights", {}).get("guidance", {}) or {}).get("items", [])),
        }
        return {
            "answer": response["answer"],
            "context": minimal_context,
            "copilot": response,
            "confidence": response.get("confidence"),
            "evidence_keys": response.get("evidence_keys"),
            "limitations": response.get("limitations"),
            "safety_status": response.get("safety_status"),
        }

    def _build_kpis(self, spending, health, alerts: list[str]) -> list[KPIItem]:
        return [
            KPIItem(
                title="Financial Health",
                value=str(health.score),
                subtitle=f"Status: {health.status}",
                tone="good" if health.status == "Healthy" else "warning" if health.status == "Moderate" else "danger",
            ),
            KPIItem(
                title="Monthly Spending",
                value=f"Rs {spending.total:,.0f}",
                subtitle=f"{spending.change_vs_last_month:+.1f}% vs last month",
                tone="neutral" if spending.change_vs_last_month <= 10 else "warning",
            ),
            KPIItem(
                title="Savings Rate",
                value=f"{health.savings_rate:.1f}%",
                subtitle="Saved from current month income",
                tone="good" if health.savings_rate >= 75 else "warning",
            ),
            KPIItem(
                title="Risk Indicator",
                value=health.risk_indicator,
                subtitle=f"{len(alerts)} active alerts",
                tone="good" if health.risk_indicator == "Low" else "danger",
            ),
        ]
