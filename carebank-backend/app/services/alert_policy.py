from __future__ import annotations


class AlertPolicy:
    def __init__(self) -> None:
        self.severity_order = {"Critical": 5, "High": 4, "Medium": 3, "Low": 2, "Info": 1}
        self.priority_order = {"Critical": 5, "High": 4, "Medium": 3, "Low": 2, "Positive": 1}
        self.default_cooldown_seconds = 900
        self.cooldown_ttl_by_type = {
            "risk_alert": 900,
            "behavior_alert": 900,
            "guidance_alert": 1200,
            "score_alert": 1800,
            "pipeline_alert": 300,
            "notification_alert": 900,
        }
        self.alert_taxonomy = {
            "risk_alert": "Risk event driven alerts",
            "behavior_alert": "Behavior drift and anomaly alerts",
            "guidance_alert": "High-priority guidance action alerts",
            "score_alert": "Financial health score degradation alerts",
            "pipeline_alert": "Realtime processing and ingestion failures",
            "notification_alert": "Notification delivery alerts",
        }

    def cooldown_for(self, alert_type: str) -> int:
        return int(self.cooldown_ttl_by_type.get(alert_type, self.default_cooldown_seconds))

    def should_emit_for_risk(self, risk_level: str, severity: str) -> bool:
        return risk_level in {"High", "Critical"} or severity in {"High", "Critical"}

    def should_emit_for_behavior(self, drift_severity: str, anomaly_severity: str, velocity: float) -> bool:
        if drift_severity in {"High", "Critical"}:
            return True
        if anomaly_severity in {"High", "Critical"}:
            return True
        return float(velocity or 0) >= 0.8

    def should_emit_for_guidance(self, priority: str, guidance_type: str) -> bool:
        if priority in {"Critical", "High"}:
            return True
        return guidance_type in {"RiskEventAction", "CashflowStability", "SpendingVelocityControl"} and priority == "Medium"

    def should_emit_for_score(self, status: str, score: float | None = None) -> bool:
        if status in {"Weak", "Critical"}:
            return True
        return score is not None and float(score) <= 30

    def suppress_noise(self, *, alert_type: str, severity: str) -> bool:
        if alert_type in {"risk_alert", "behavior_alert", "guidance_alert", "score_alert", "pipeline_alert"}:
            return severity in {"Low", "Info"}
        return False
