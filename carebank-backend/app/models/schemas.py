from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class UserContext(BaseModel):
    id: str
    email: str | None = None


class Transaction(BaseModel):
    date: str
    description: str
    amount: float
    category: str


class ManualTransactionRequest(BaseModel):
    date: str
    description: str = Field(min_length=1)
    amount: float = Field(gt=0)
    category: str | None = None


class ScoreBreakdown(BaseModel):
    savings_score: float = Field(ge=0, le=100)
    stability_score: float = Field(ge=0, le=100)
    discipline_score: float = Field(ge=0, le=100)
    risk_score: float = Field(ge=0, le=100)


class ScoreMetrics(BaseModel):
    savings_ratio: float
    income: float
    expenses: float
    expense_volatility: float
    high_value_expense_count: int
    impulse_spend_count: int
    expense_ratio: float
    net_balance_trend: float


class ScoreContribution(BaseModel):
    component: str
    raw_score: float
    weight: float
    weighted_points: float
    explanation: str
    source_signals: list[str] = Field(default_factory=list)


class ScorePenalty(BaseModel):
    penalty_type: str
    points_deducted: float
    reason: str
    source_signal: str
    severity: str


class ScoreExplainability(BaseModel):
    scoring_version: str
    contributions: list[ScoreContribution] = Field(default_factory=list)
    penalties: list[ScorePenalty] = Field(default_factory=list)
    final_score_formula: str
    source_summary: list[str] = Field(default_factory=list)


class ScoreConfidence(BaseModel):
    confidence_score: float = Field(ge=0, le=1)
    data_quality_score: float = Field(ge=0, le=1)
    history_depth: int
    transaction_count: int
    valid_transaction_ratio: float = Field(ge=0, le=1)
    limitations: list[str] = Field(default_factory=list)


class FinancialScoreResponse(BaseModel):
    score: float = Field(ge=0, le=100)
    status: str
    breakdown: ScoreBreakdown
    metrics: ScoreMetrics
    summary: str
    major_issues: list[str] = Field(default_factory=list)
    positive_signals: list[str] = Field(default_factory=list)
    risk_timeline: list[dict[str, Any]] = Field(default_factory=list)
    scoring_version: str = "carebank-score-v1.0"
    explainability: ScoreExplainability = Field(
        default_factory=lambda: ScoreExplainability(
            scoring_version="carebank-score-v1.0",
            final_score_formula="weighted_components - penalties",
        )
    )
    confidence: ScoreConfidence = Field(
        default_factory=lambda: ScoreConfidence(
            confidence_score=0.5,
            data_quality_score=0.5,
            history_depth=0,
            transaction_count=0,
            valid_transaction_ratio=0.0,
            limitations=[],
        )
    )


class SimulationRequest(BaseModel):
    amount: float = Field(gt=0)
    window_days: int = Field(default=30, ge=1, le=365)
    safety_threshold: float = Field(default=5000.0, ge=0)


class SimulationResponse(BaseModel):
    current_balance: float
    projected_income: float
    projected_expenses: float
    simulated_cost: float
    future_balance: float
    decision: str
    reason: str
    suggestion: str
    window_days: int
    safety_threshold: float
    ai_explanation: str


class FraudFinding(BaseModel):
    description: str
    amount: float
    risk: str
    flags: list[str]


class FraudCheckResponse(BaseModel):
    flagged_transactions: list[FraudFinding]


class FinancialHealth(BaseModel):
    score: int = Field(ge=0, le=100)
    status: str
    risk_indicator: str
    summary: str
    savings_rate: float
    breakdown: ScoreBreakdown
    metrics: ScoreMetrics
    scoring_version: str = "carebank-score-v1.0"
    explainability: ScoreExplainability = Field(
        default_factory=lambda: ScoreExplainability(
            scoring_version="carebank-score-v1.0",
            final_score_formula="weighted_components - penalties",
        )
    )
    confidence: ScoreConfidence = Field(
        default_factory=lambda: ScoreConfidence(
            confidence_score=0.5,
            data_quality_score=0.5,
            history_depth=0,
            transaction_count=0,
            valid_transaction_ratio=0.0,
            limitations=[],
        )
    )


class SpendingSummary(BaseModel):
    Food: float
    Shopping: float
    Travel: float
    Bills: float
    total: float
    change_vs_last_month: float
    largest_category: str


class KPIItem(BaseModel):
    title: str
    value: str
    subtitle: str
    tone: str


class AnalysisResponse(BaseModel):
    financial_health: FinancialHealth
    spending: SpendingSummary
    alerts: list[str]
    recommendations: list[str]
    ai_explanation: str
    kpis: list[KPIItem]
    chart_data: list[dict[str, Any]]
    insights: dict[str, Any]


class ChatRequest(BaseModel):
    message: str


class CopilotResponse(BaseModel):
    answer: str
    intent: str
    confidence: float | None = None
    evidence_keys: list[str] = Field(default_factory=list)
    referenced_values: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    safety_status: str
    fallback_used: bool
    generated_at: str


class ChatResponse(BaseModel):
    answer: str
    context: dict[str, Any] | None = None
    copilot: CopilotResponse | None = None
    confidence: float | None = None
    evidence_keys: list[str] | None = None
    limitations: list[str] | None = None
    safety_status: str | None = None


class CsvUploadRequest(BaseModel):
    filename: str
    content: str


class CsvUploadResponse(BaseModel):
    inserted_count: int
    skipped_count: int
    errors: list[str]
    fraud_summary: list[FraudFinding] = Field(default_factory=list)


class ManualTransactionResponse(BaseModel):
    inserted_count: int
    fraud_summary: list[FraudFinding] = Field(default_factory=list)


class NotificationPreferences(BaseModel):
    overspending_alerts: bool = True
    weekly_wellness_summary: bool = True
    ai_assistant_tips: bool = False


class PreferencesResponse(BaseModel):
    preferences: NotificationPreferences


class GuidanceItem(BaseModel):
    guidance_id: str
    guidance_type: str
    priority: str
    confidence: float = Field(ge=0, le=1)
    actionability_score: float = Field(ge=0, le=1)
    title: str
    rationale: str
    action_steps: list[str] = Field(default_factory=list)
    expected_impact: str
    source_signals: list[str] = Field(default_factory=list)
    related_risk_events: list[str] = Field(default_factory=list)
    ttl_days: int
    created_at: str
    ttl_seconds: int = 0
    risk_event_ids: list[str] = Field(default_factory=list)


class GuidanceResponse(BaseModel):
    generated_at: str
    items: list[GuidanceItem]
    top_priority: str
    summary: str
    engine_version: str
    guidance_items: list[GuidanceItem] = Field(default_factory=list)


class CategoryDrift(BaseModel):
    category: str
    baseline_amount: float
    current_amount: float
    drift_percentage: float
    severity: str


class MerchantRecurrence(BaseModel):
    merchant: str
    transaction_count: int
    average_interval_days: float
    recurrence_confidence: float = Field(ge=0, le=1)
    expected_next_date: str | None = None
    recurrence_type: str


class BehaviorAnomalyEvent(BaseModel):
    event_type: str
    severity: str
    confidence: float = Field(ge=0, le=1)
    evidence: dict[str, Any] = Field(default_factory=dict)
    recommendation_hint: str


class BehaviorBaseline(BaseModel):
    average_transaction_amount: float = 0.0
    median_transaction_amount: float = 0.0
    average_daily_spend: float = 0.0
    average_weekly_spend: float = 0.0
    usual_active_hours: list[int] = Field(default_factory=list)
    weekend_spend_ratio: float = 0.0
    top_merchants: list[str] = Field(default_factory=list)
    recurring_merchants: list[str] = Field(default_factory=list)
    category_baselines: dict[str, float] = Field(default_factory=dict)


class BehavioralIntelligenceResult(BaseModel):
    transaction_count: int = 0
    valid_transaction_count: int = 0
    parse_errors: list[str] = Field(default_factory=list)
    category_totals: dict[str, float] = Field(default_factory=dict)
    category_percentages: dict[str, float] = Field(default_factory=dict)
    top_categories: list[str] = Field(default_factory=list)
    category_transaction_counts: dict[str, int] = Field(default_factory=dict)
    category_baselines: dict[str, float] = Field(default_factory=dict)
    last_7_days_spend: float = 0.0
    last_30_days_spend: float = 0.0
    last_90_days_spend: float = 0.0
    previous_30_days_spend: float = 0.0
    spend_velocity_7d_vs_30d: float = 0.0
    month_over_month_change: float = 0.0
    baseline: BehaviorBaseline = Field(default_factory=BehaviorBaseline)
    category_drift: list[CategoryDrift] = Field(default_factory=list)
    drift_score: float = 0.0
    drift_severity: str = "Stable"
    merchant_recurrence: list[MerchantRecurrence] = Field(default_factory=list)
    anomaly_events: list[BehaviorAnomalyEvent] = Field(default_factory=list)
    trend_timeline: list[dict[str, Any]] = Field(default_factory=list)
    rolling_spend: dict[str, float] = Field(default_factory=dict)
    weekend_spending_drift: float = 0.0
    anomaly_score: float = 0.0
    evidence: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)


class RiskEvent(BaseModel):
    risk_event_id: str
    event_type: str
    risk_type: str
    severity: str
    confidence: float = Field(ge=0, le=1)
    evidence: dict[str, Any] = Field(default_factory=dict)
    recommendation: str
    source_signals: list[str] = Field(default_factory=list)
    created_at: str


class RiskIntelligenceResult(BaseModel):
    overall_risk_score: float = Field(ge=0, le=100)
    risk_level: str
    confidence: float = Field(ge=0, le=1)
    risk_events: list[RiskEvent] = Field(default_factory=list)
    risk_signals: list[str] = Field(default_factory=list)
    evidence_summary: str
    recommendation_text: str
    generated_at: str
    engine_version: str


class SystemEvent(BaseModel):
    event_id: str
    event_type: str
    user_id: str
    correlation_id: str
    idempotency_key: str
    payload: dict[str, Any] = Field(default_factory=dict)
    status: str = "pending"
    attempt_count: int = 0
    max_attempts: int = 3
    created_at: str
    updated_at: str | None = None


class LiveAlertEvent(BaseModel):
    alert_id: str
    user_id: str
    correlation_id: str
    severity: str
    title: str
    message: str
    source: str
    alert_type: str = "notification_alert"
    semantic_signature: str = ""
    delivery_status: str = "created"
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: str
