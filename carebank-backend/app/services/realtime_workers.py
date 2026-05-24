from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha1
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.models.schemas import LiveAlertEvent, SystemEvent
from app.services.alert_dedupe_store import AlertDedupeStore
from app.services.alert_policy import AlertPolicy
from app.services.event_store import EventStore
from app.services.notification_agent import NotificationAgent
from app.services.preferences import PreferenceStore
from app.services.realtime_manager import get_realtime_manager
from app.services.redaction import redact_dict


class RealtimeWorkers:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.store = EventStore(Path(__file__).resolve().parents[2])
        self.manager = get_realtime_manager()
        self.policy = AlertPolicy()
        self.dedupe = AlertDedupeStore()
        self.preferences = PreferenceStore(self.settings.preferences_path)
        self.notification_agent = NotificationAgent()

    async def dispatch(self, event: SystemEvent) -> list[SystemEvent]:
        if event.event_type == "transaction_ingested":
            return await self._handle_transaction_ingested(event)
        if event.event_type in {"analysis_completed", "risk_detected", "guidance_generated"}:
            return self._intelligence_alerts(event)
        if event.event_type == "alert_created":
            await self._handle_alert_created(event)
            return []
        if event.event_type in {"analysis_failed", "processing_failed", "dlq_event"}:
            await self._emit_pipeline_alert(event)
            return []
        return []

    def _intelligence_alerts(self, event: SystemEvent) -> list[SystemEvent]:
        generated: list[SystemEvent] = []
        payload = event.payload or {}

        risk_level = str(payload.get("risk_level") or payload.get("overall_risk_level") or "")
        risk_severity = str(payload.get("risk_severity") or "")
        if self.policy.should_emit_for_risk(risk_level, risk_severity):
            generated.append(
                self._child_event(
                    event,
                    "alert_created",
                    {
                        "alert_type": "risk_alert",
                        "severity": "Critical" if risk_level == "Critical" else "High",
                        "title": "Elevated financial risk detected",
                        "message": str(payload.get("recommendation_text") or "High severity risk signals need action."),
                        "source": "risk_intelligence",
                        "evidence": {"risk_level": risk_level, "risk_severity": risk_severity},
                    },
                )
            )

        drift_severity = str(payload.get("drift_severity") or "")
        anomaly_severity = str(payload.get("anomaly_severity") or "")
        velocity = float(payload.get("spend_velocity_7d_vs_30d") or 0)
        if self.policy.should_emit_for_behavior(drift_severity, anomaly_severity, velocity):
            generated.append(
                self._child_event(
                    event,
                    "alert_created",
                    {
                        "alert_type": "behavior_alert",
                        "severity": "High" if drift_severity in {"High", "Critical"} or anomaly_severity in {"High", "Critical"} else "Medium",
                        "title": "Behavior drift alert",
                        "message": "Spending behavior shifted from baseline and requires review.",
                        "source": "behavior_intelligence",
                        "evidence": {
                            "drift_severity": drift_severity,
                            "anomaly_severity": anomaly_severity,
                            "spend_velocity_7d_vs_30d": velocity,
                        },
                    },
                )
            )

        guidance_priority = str(payload.get("guidance_priority") or payload.get("top_priority") or "")
        guidance_type = str(payload.get("guidance_type") or "")
        if self.policy.should_emit_for_guidance(guidance_priority, guidance_type):
            generated.append(
                self._child_event(
                    event,
                    "alert_created",
                    {
                        "alert_type": "guidance_alert",
                        "severity": "High" if guidance_priority in {"Critical", "High"} else "Medium",
                        "title": "High-priority guidance available",
                        "message": "A high-priority guidance item needs your attention.",
                        "source": "guidance_engine",
                        "evidence": {"priority": guidance_priority, "guidance_type": guidance_type},
                    },
                )
            )

        score_status = str(payload.get("score_status") or payload.get("status") or "")
        score_value = payload.get("score")
        if self.policy.should_emit_for_score(score_status, float(score_value) if score_value is not None else None):
            generated.append(
                self._child_event(
                    event,
                    "alert_created",
                    {
                        "alert_type": "score_alert",
                        "severity": "High" if score_status == "Weak" else "Critical",
                        "title": "Financial health score warning",
                        "message": f"Financial score status is {score_status or 'elevated risk'}.",
                        "source": "financial_health",
                        "evidence": {"score_status": score_status, "score": score_value},
                    },
                )
            )

        return generated

    async def _handle_transaction_ingested(self, event: SystemEvent) -> list[SystemEvent]:
        now = datetime.now(UTC).isoformat()
        started = self._child_event(event, "analysis_started", {"source_event_id": event.event_id, "ts": now})
        completed = self._child_event(
            event,
            "analysis_completed",
            {"source_event_id": event.event_id, "inserted_count": event.payload.get("inserted_count", 0), "ts": now},
        )
        generated: list[SystemEvent] = [started, completed]
        inserted = int(event.payload.get("inserted_count") or 0)

        if inserted > 0:
            generated.append(self._child_event(event, "guidance_generated", {"inserted_count": inserted}))

        if inserted >= 5:
            generated.append(
                self._child_event(
                    event,
                    "alert_created",
                    {
                        "alert_type": "pipeline_alert",
                        "severity": "Medium",
                        "title": "New transaction activity",
                        "message": f"{inserted} transactions were ingested.",
                        "source": "realtime_worker",
                        "evidence": {"inserted_count": inserted},
                    },
                )
            )
        return generated

    async def _emit_pipeline_alert(self, event: SystemEvent) -> None:
        alert_event = self._child_event(
            event,
            "alert_created",
            {
                "alert_type": "pipeline_alert",
                "severity": "High",
                "title": "Pipeline processing issue",
                "message": f"Event {event.event_type} requires review.",
                "source": "realtime_pipeline",
                "evidence": {"event_id": event.event_id, "event_type": event.event_type},
            },
        )
        await self._handle_alert_created(alert_event)

    async def _handle_alert_created(self, event: SystemEvent) -> None:
        alert_type = str(event.payload.get("alert_type") or "notification_alert")
        severity = str(event.payload.get("severity") or "Low")
        source = str(event.payload.get("source") or "realtime_pipeline")
        evidence = event.payload.get("evidence") or {"event_id": event.event_id}
        semantic_signature = str(event.payload.get("semantic_signature") or self.dedupe.make_signature(source, evidence))

        if self.policy.suppress_noise(alert_type=alert_type, severity=severity):
            return

        stable_raw = f"{event.user_id}:{alert_type}:{semantic_signature}:{event.correlation_id}"
        alert_id = f"alert_{sha1(stable_raw.encode('utf-8')).hexdigest()[:12]}"

        if self.dedupe.should_suppress(event.user_id, alert_type, semantic_signature):
            suppressed = LiveAlertEvent(
                alert_id=alert_id,
                user_id=event.user_id,
                correlation_id=event.correlation_id,
                severity=severity,
                title=str(event.payload.get("title") or "CareBank Alert"),
                message=str(event.payload.get("message") or "An event requires your attention."),
                source=source,
                alert_type=alert_type,
                semantic_signature=semantic_signature,
                delivery_status="suppressed",
                payload=redact_dict({"event_id": event.event_id, "event_type": event.event_type}),
                created_at=datetime.now(UTC).isoformat(),
            )
            self.store.persist_live_alert(suppressed)
            self.store.persist_audit_log(
                "notification_suppressed",
                {"user_id": event.user_id, "alert_id": alert_id, "alert_type": alert_type, "correlation_id": event.correlation_id},
            )
            return

        self.dedupe.mark_sent(event.user_id, alert_type, semantic_signature, self.policy.cooldown_for(alert_type))

        alert = LiveAlertEvent(
            alert_id=alert_id,
            user_id=event.user_id,
            correlation_id=event.correlation_id,
            severity=severity,
            title=str(event.payload.get("title") or "CareBank Alert"),
            message=str(event.payload.get("message") or "An event requires your attention."),
            source=source,
            alert_type=alert_type,
            semantic_signature=semantic_signature,
            delivery_status="created",
            payload=redact_dict({"event_id": event.event_id, "event_type": event.event_type}),
            created_at=datetime.now(UTC).isoformat(),
        )
        self.store.persist_live_alert(alert)

        prefs = self.preferences.get(event.user_id)
        realtime_enabled = bool(getattr(prefs, "overspending_alerts", True))
        email_enabled = bool(getattr(prefs, "weekly_wellness_summary", False))

        delivered = False
        if realtime_enabled:
            await self.manager.send_to_user(
                event.user_id,
                {
                    "type": "live_alert",
                    "alert_id": alert.alert_id,
                    "severity": alert.severity,
                    "title": alert.title,
                    "message": alert.message,
                    "source": alert.source,
                    "alert_type": alert.alert_type,
                    "delivery_status": "delivered",
                    "correlation_id": alert.correlation_id,
                    "created_at": alert.created_at,
                },
            )
            delivered = True

        if email_enabled:
            self.notification_agent.queue_notification(
                alert_id=alert.alert_id,
                user_id=event.user_id,
                channel="email",
                payload={
                    "title": alert.title,
                    "message": alert.message,
                    "severity": alert.severity,
                    "alert_type": alert.alert_type,
                },
            )
            self.notification_agent.process_next()

        status = "delivered" if delivered else ("queued" if email_enabled else "created")
        alert.delivery_status = status
        self.store.persist_live_alert(alert)
        self.store.persist_processing_event(event, stage="alert_delivery", status=status)

    @staticmethod
    def _child_event(parent: SystemEvent, event_type: str, payload: dict[str, Any]) -> SystemEvent:
        raw = f"{event_type}:{parent.user_id}:{parent.correlation_id}:{payload.get('source_event_id', parent.event_id)}"
        event_id = f"evt_{sha1(raw.encode('utf-8')).hexdigest()[:16]}"
        return SystemEvent(
            event_id=event_id,
            event_type=event_type,
            user_id=parent.user_id,
            correlation_id=parent.correlation_id,
            idempotency_key=f"{event_type}:{parent.user_id}:{parent.correlation_id}",
            payload=payload,
            status="pending",
            attempt_count=0,
            max_attempts=parent.max_attempts,
            created_at=datetime.now(UTC).isoformat(),
            updated_at=None,
        )
