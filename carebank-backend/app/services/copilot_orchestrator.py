from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any

from app.services.copilot_policy import CopilotPolicy
from app.services.llm import LLMService
from app.services.redaction import redact_dict
from app.services.security_audit import SecurityAuditLogger


class CopilotOrchestrator:
    def __init__(self) -> None:
        self.llm = LLMService()
        self.policy = CopilotPolicy()
        self.audit = SecurityAuditLogger()

    async def respond(self, message: str, analysis_payload: dict[str, Any]) -> dict[str, Any]:
        intent = self.policy.classify_intent(message)
        if intent == "prompt_injection_attempt":
            self.audit.log_prompt_injection(message)
            return self._refusal(intent, "blocked_prompt_injection")
        if intent in {"unsupported_investment_advice", "unsupported_legal_or_tax_advice"}:
            self.audit.log_unsupported_advice(intent, message)
            return self._refusal(intent, "blocked_unsupported_advice")

        scoped = self._scoped_context(analysis_payload, intent)
        allowed_keys = set(self._allowed_evidence_keys(scoped))
        llm_raw = await self.llm.answer_question_structured(message, redact_dict(scoped))
        if not llm_raw:
            self.audit.log_copilot_fallback("llm_unavailable", {"intent": intent})
            return self._fallback(intent, scoped, "llm_unavailable")

        parsed = self._validate_structured_output(llm_raw, allowed_keys)
        if parsed is None:
            self.audit.log_llm_validation_failure("invalid_structured_output", llm_raw)
            return self._fallback(intent, scoped, "invalid_structured_output")

        numeric_ok, referenced_values = self._verify_numeric_claims(parsed["answer"], scoped)
        if not numeric_ok:
            self.audit.log_llm_validation_failure("numeric_claim_mismatch", llm_raw)
            return self._fallback(intent, scoped, "numeric_claim_mismatch")

        return {
            "answer": parsed["answer"],
            "intent": intent,
            "confidence": parsed["confidence"],
            "evidence_keys": parsed["evidence_keys"],
            "referenced_values": referenced_values,
            "limitations": parsed["limitations"],
            "safety_status": "grounded",
            "fallback_used": False,
            "generated_at": datetime.now(UTC).isoformat(),
        }

    def _intent(self, message: str) -> str:
        return self.policy.classify_intent(message)

    def _scoped_context(self, payload: dict[str, Any], intent: str | None = None) -> dict[str, Any]:
        risk = payload.get("insights", {}).get("risk_intelligence", {}) if isinstance(payload.get("insights"), dict) else {}
        typed_risk = risk.get("typed", {}) if isinstance(risk, dict) else {}
        top_events = typed_risk.get("risk_events", [])[:3] if isinstance(typed_risk, dict) else []
        guidance = payload.get("insights", {}).get("guidance", {}) if isinstance(payload.get("insights"), dict) else {}
        guidance_items = (guidance.get("items") or guidance.get("guidance_items") or [])[:5] if isinstance(guidance, dict) else []
        behavior = payload.get("insights", {}).get("behavior", {}) if isinstance(payload.get("insights"), dict) else {}
        scoring = {
            "score": payload.get("financial_health", {}).get("score"),
            "status": payload.get("financial_health", {}).get("status"),
            "scoring_version": payload.get("financial_health", {}).get("scoring_version"),
            "top_contributions": (payload.get("financial_health", {}).get("explainability", {}).get("contributions", [])[:3]),
            "top_penalties": (payload.get("financial_health", {}).get("explainability", {}).get("penalties", [])[:3]),
            "confidence_score": payload.get("financial_health", {}).get("confidence", {}).get("confidence_score"),
            "data_quality_score": payload.get("financial_health", {}).get("confidence", {}).get("data_quality_score"),
            "limitations": payload.get("financial_health", {}).get("confidence", {}).get("limitations", []),
        }
        risk_context = {
            "overall_risk_score": typed_risk.get("overall_risk_score", risk.get("overall_risk_score")),
            "risk_level": typed_risk.get("risk_level", risk.get("risk_level")),
            "confidence": typed_risk.get("confidence", risk.get("confidence")),
            "top_risk_events": top_events,
            "evidence_summary": typed_risk.get("evidence_summary", risk.get("evidence_summary")),
            "recommendation_text": typed_risk.get("recommendation_text", risk.get("mitigation_suggestion")),
            "source_signals": typed_risk.get("risk_signals", risk.get("source_signals", [])),
        }
        guidance_context = [
            {
                "guidance_type": item.get("guidance_type"),
                "priority": item.get("priority"),
                "title": item.get("title"),
                "action_steps": item.get("action_steps", []),
                "expected_impact": item.get("expected_impact"),
                "confidence": item.get("confidence"),
                "related_risk_events": item.get("related_risk_events", item.get("risk_event_ids", [])),
            }
            for item in guidance_items
        ]
        spending_context = {
            "totals": payload.get("spending", {}),
            "top_categories": behavior.get("top_categories", []),
            "last_7_days_spend": behavior.get("last_7_days_spend"),
            "last_30_days_spend": behavior.get("last_30_days_spend"),
            "last_90_days_spend": behavior.get("last_90_days_spend"),
        }
        behavior_context = {
            "drift_score": behavior.get("drift_score"),
            "drift_severity": behavior.get("drift_severity"),
            "anomaly_events": behavior.get("anomaly_events", [])[:5],
            "merchant_recurrence": behavior.get("merchant_recurrence", [])[:5],
        }
        simulation_context = payload.get("simulation", {})

        if intent == "financial_health_query":
            return {"scoring": scoring}
        if intent == "risk_explanation":
            return {"risk_intelligence": risk_context}
        if intent == "guidance_explanation":
            return {"guidance": guidance_context}
        if intent == "spending_summary":
            return {"spending": spending_context}
        if intent == "behavior_drift_explanation":
            return {"behavior": behavior_context}
        if intent == "simulation_explanation":
            return {"simulation": simulation_context}
        if intent == "general_financial_question":
            return {"scoring": scoring, "risk_intelligence": risk_context, "guidance": guidance_context[:3]}

        return {
            "financial_health": payload.get("financial_health", {}),
            "spending": payload.get("spending", {}),
            "alerts": payload.get("alerts", []),
            "recommendations": payload.get("recommendations", []),
            "scoring": scoring,
            "risk_intelligence": risk_context,
            "guidance": guidance_context,
            "behavior": behavior_context,
        }

    def _allowed_evidence_keys(self, context: dict[str, Any], prefix: str = "") -> list[str]:
        keys: list[str] = []
        for key, value in context.items():
            full_key = f"{prefix}.{key}" if prefix else key
            keys.append(full_key)
            if isinstance(value, dict):
                keys.extend(self._allowed_evidence_keys(value, full_key))
        return keys

    def _validate_structured_output(self, raw_response: str, allowed_keys: set[str]) -> dict[str, Any] | None:
        try:
            data = json.loads(raw_response)
        except json.JSONDecodeError:
            return None
        if not isinstance(data, dict):
            return None
        answer = data.get("answer")
        confidence = data.get("confidence")
        evidence_keys = data.get("evidence_keys")
        limitations = data.get("limitations")
        if not isinstance(answer, str) or not answer.strip():
            return None
        try:
            confidence_value = max(0.0, min(1.0, float(confidence)))
        except (TypeError, ValueError):
            return None
        if not isinstance(evidence_keys, list) or not all(isinstance(item, str) for item in evidence_keys):
            return None
        if not isinstance(limitations, list) or not all(isinstance(item, str) for item in limitations):
            return None
        if any(item not in allowed_keys for item in evidence_keys):
            return None
        return {
            "answer": answer.strip(),
            "confidence": round(confidence_value, 4),
            "evidence_keys": evidence_keys,
            "limitations": limitations,
        }

    def _verify_numeric_claims(self, answer: str, context: dict[str, Any]) -> tuple[bool, list[str]]:
        context_values = self._collect_numeric_strings(context)
        referenced_values = [value for value in self._extract_numeric_tokens(answer) if value in context_values]
        extracted = self._extract_numeric_tokens(answer)
        if not extracted:
            return True, []
        is_supported = all(value in context_values for value in extracted)
        return is_supported, referenced_values

    def _collect_numeric_strings(self, payload: Any) -> set[str]:
        values: set[str] = set()
        if isinstance(payload, dict):
            for item in payload.values():
                values.update(self._collect_numeric_strings(item))
        elif isinstance(payload, list):
            for item in payload:
                values.update(self._collect_numeric_strings(item))
        elif isinstance(payload, (int, float)):
            values.add(str(int(payload)) if float(payload).is_integer() else str(round(float(payload), 2)))
        return values

    def _extract_numeric_tokens(self, text: str) -> list[str]:
        raw = re.findall(r"(?:₹\s*)?\d+(?:\.\d+)?%?", text or "")
        normalized: list[str] = []
        for token in raw:
            clean = token.replace("₹", "").replace("%", "").strip()
            if clean:
                normalized.append(clean)
        return normalized

    def _refusal(self, intent: str, safety_status: str) -> dict[str, Any]:
        return {
            "answer": "I can only explain your deterministic CareBank analysis and cannot provide that type of advice.",
            "intent": intent,
            "confidence": 0.99,
            "evidence_keys": [],
            "referenced_values": [],
            "limitations": [intent],
            "safety_status": safety_status,
            "fallback_used": False,
            "generated_at": datetime.now(UTC).isoformat(),
        }

    def _fallback(self, intent: str, scoped: dict[str, Any], reason: str) -> dict[str, Any]:
        answer = self._fallback_answer(intent, scoped)
        return {
            "answer": answer,
            "intent": intent,
            "confidence": 0.55,
            "evidence_keys": self._allowed_evidence_keys(scoped)[:3],
            "referenced_values": self._extract_numeric_tokens(answer),
            "limitations": [f"fallback:{reason}", "Deterministic backend is source of truth"],
            "safety_status": "fallback_used",
            "fallback_used": True,
            "generated_at": datetime.now(UTC).isoformat(),
        }

    def _fallback_answer(self, intent: str, scoped: dict[str, Any]) -> str:
        if intent == "financial_health_query":
            score = scoped.get("scoring", {}).get("score")
            status = scoped.get("scoring", {}).get("status")
            return f"Your financial health score is {score} with status {status}. This explanation is grounded in deterministic CareBank analysis."
        if intent == "risk_explanation":
            risk_level = scoped.get("risk_intelligence", {}).get("risk_level")
            score = scoped.get("risk_intelligence", {}).get("overall_risk_score")
            return f"Your current risk level is {risk_level} with risk score {score}. Review top risk events to reduce near-term risk."
        if intent == "guidance_explanation":
            items = scoped.get("guidance", [])
            first = items[0]["title"] if items else "Review priority guidance"
            return f"Top guidance item: {first}. Follow the listed action steps to improve financial health."
        if intent == "spending_summary":
            totals = scoped.get("spending", {}).get("totals", {})
            total = totals.get("total")
            return f"Your recent spending summary shows total spend of {total}. Focus on top categories to control month-over-month changes."
        if intent == "behavior_drift_explanation":
            drift = scoped.get("behavior", {}).get("drift_score")
            sev = scoped.get("behavior", {}).get("drift_severity")
            return f"Behavior drift score is {drift} with severity {sev}. Monitor anomalies and recurring merchant patterns for stability."
        return "I can explain only from available CareBank analysis. Please ask about your score, risk, spending, behavior, or guidance signals."

