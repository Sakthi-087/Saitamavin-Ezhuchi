from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta
from statistics import mean, median, pstdev
from typing import Any

from app.models.schemas import BehaviorAnomalyEvent, BehaviorBaseline, BehavioralIntelligenceResult, CategoryDrift, MerchantRecurrence
from app.services.transaction_utils import is_income_category


class BehavioralIntelligenceEngine:
    HIGH_VALUE_THRESHOLD = 2000.0

    def analyze_behavior(self, transactions: list[dict[str, Any]]) -> BehavioralIntelligenceResult:
        normalized, parse_errors = self._normalize_transactions(transactions)
        expense_tx = [tx for tx in normalized if not self._is_non_expense(tx)]
        expense_tx.sort(key=lambda tx: tx["dt"])

        if not expense_tx:
            return BehavioralIntelligenceResult(
                transaction_count=len(transactions),
                valid_transaction_count=len(normalized),
                parse_errors=parse_errors,
                baseline=BehaviorBaseline(),
                rolling_spend={"last_7_days_spend": 0.0, "last_30_days_spend": 0.0, "last_90_days_spend": 0.0, "previous_30_days_spend": 0.0},
            )

        anchor = expense_tx[-1]["dt"].date()
        windows = self._rolling_windows(expense_tx, anchor)
        category = self._category_intelligence(expense_tx, anchor)
        recurrence = self._merchant_recurrence(expense_tx)
        baseline = self._baseline(expense_tx, category["category_baselines"], recurrence)
        drift = self._category_drift(category["category_totals"], category["category_baselines"])
        anomalies = self._anomaly_events(expense_tx, windows, drift["drifts"], baseline, recurrence)
        trend_timeline = self._trend_timeline(expense_tx)

        result = BehavioralIntelligenceResult(
            transaction_count=len(transactions),
            valid_transaction_count=len(normalized),
            parse_errors=parse_errors,
            category_totals=category["category_totals"],
            category_percentages=category["category_percentages"],
            category_transaction_counts=category["category_transaction_counts"],
            top_categories=category["top_categories"],
            category_baselines=category["category_baselines"],
            last_7_days_spend=round(windows["last_7_days_spend"], 2),
            last_30_days_spend=round(windows["last_30_days_spend"], 2),
            last_90_days_spend=round(windows["last_90_days_spend"], 2),
            previous_30_days_spend=round(windows["previous_30_days_spend"], 2),
            spend_velocity_7d_vs_30d=round(windows["spend_velocity_7d_vs_30d"], 4),
            month_over_month_change=round(windows["month_over_month_change"], 4),
            baseline=baseline,
            category_drift=drift["drifts"],
            drift_score=round(drift["drift_score"], 2),
            drift_severity=drift["drift_severity"],
            merchant_recurrence=recurrence,
            anomaly_events=anomalies,
            trend_timeline=trend_timeline,
            rolling_spend=windows,
            weekend_spending_drift=round(baseline.weekend_spend_ratio, 4),
            anomaly_score=round(self._anomaly_score(anomalies), 4),
            evidence=["rolling_windows", "category_drift", "merchant_recurrence", "anomaly_events"],
            metrics={
                "drift_score": round(drift["drift_score"], 2),
                "drift_severity": drift["drift_severity"],
                "anomaly_count": len(anomalies),
                "weekend_spending_drift": round(baseline.weekend_spend_ratio, 4),
            },
        )
        return result

    def analyze(self, transactions: list[dict[str, Any]]) -> dict[str, Any]:
        result = self.analyze_behavior(transactions)
        payload = result.model_dump()
        payload["rolling_spend_windows"] = {
            "7d_avg": round(result.last_7_days_spend / 7.0, 2),
            "30d_avg": round(result.last_30_days_spend / 30.0, 2),
        }
        payload["spending_velocity"] = result.spend_velocity_7d_vs_30d
        payload["habit_recurrence"] = round(
            mean([item.recurrence_confidence for item in result.merchant_recurrence]), 4
        ) if result.merchant_recurrence else 0.0
        return payload

    def _normalize_transactions(self, transactions: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
        normalized: list[dict[str, Any]] = []
        parse_errors: list[str] = []
        for index, tx in enumerate(transactions):
            try:
                dt = self._parse_datetime(tx.get("date") or tx.get("created_at") or "")
            except ValueError as exc:
                parse_errors.append(f"row_{index}: {exc}")
                continue
            try:
                amount = float(tx.get("amount"))
            except (TypeError, ValueError):
                parse_errors.append(f"row_{index}: invalid amount '{tx.get('amount')}'")
                continue
            category = str(tx.get("category") or "Uncategorized").strip() or "Uncategorized"
            normalized.append(
                {
                    "dt": dt,
                    "date": dt.date(),
                    "hour": dt.hour,
                    "amount": amount,
                    "expense_amount": abs(amount),
                    "category": category.title(),
                    "description": str(tx.get("description") or "Unknown").strip() or "Unknown",
                    "transaction_type": str(tx.get("transaction_type") or "").strip().lower(),
                }
            )
        return normalized, parse_errors

    def _is_non_expense(self, tx: dict[str, Any]) -> bool:
        tx_type = str(tx.get("transaction_type") or "").lower()
        if tx_type in {"credit", "income", "refund"}:
            return True
        category = str(tx.get("category") or "")
        if is_income_category(category):
            return True
        return float(tx.get("amount") or 0.0) < 0

    def _rolling_windows(self, transactions: list[dict[str, Any]], anchor: date) -> dict[str, float]:
        def in_range(d: date, start_days_ago: int, end_days_ago: int) -> bool:
            start = anchor - timedelta(days=start_days_ago)
            end = anchor - timedelta(days=end_days_ago)
            return start <= d <= end

        def window_sum(start_days_ago: int, end_days_ago: int) -> float:
            return sum(float(tx["expense_amount"]) for tx in transactions if in_range(tx["date"], start_days_ago, end_days_ago))

        last_7 = window_sum(6, 0)
        last_30 = window_sum(29, 0)
        last_90 = window_sum(89, 0)
        prev_30 = window_sum(59, 30)
        avg_7 = last_7 / 7.0
        avg_30 = last_30 / 30.0
        velocity = 0.0 if avg_30 == 0 else (avg_7 - avg_30) / avg_30
        mom = 0.0 if prev_30 == 0 else (last_30 - prev_30) / prev_30
        return {
            "last_7_days_spend": last_7,
            "last_30_days_spend": last_30,
            "last_90_days_spend": last_90,
            "previous_30_days_spend": prev_30,
            "spend_velocity_7d_vs_30d": velocity,
            "month_over_month_change": mom,
        }

    def _category_intelligence(self, transactions: list[dict[str, Any]], anchor: date) -> dict[str, Any]:
        category_totals: dict[str, float] = defaultdict(float)
        category_counts: dict[str, int] = defaultdict(int)
        baseline_totals: dict[str, float] = defaultdict(float)
        total_spend = 0.0
        for tx in transactions:
            category = str(tx["category"])
            amount = float(tx["expense_amount"])
            category_totals[category] += amount
            category_counts[category] += 1
            total_spend += amount
            if anchor - timedelta(days=59) <= tx["date"] <= anchor - timedelta(days=30):
                baseline_totals[category] += amount
        category_percentages = {
            key: round((value / total_spend) * 100.0, 4) if total_spend > 0 else 0.0
            for key, value in category_totals.items()
        }
        top_categories = sorted(category_totals.items(), key=lambda item: item[1], reverse=True)[:5]
        return {
            "category_totals": {k: round(v, 2) for k, v in category_totals.items()},
            "category_percentages": category_percentages,
            "category_transaction_counts": dict(category_counts),
            "top_categories": [name for name, _ in top_categories],
            "category_baselines": {k: round(v, 2) for k, v in baseline_totals.items()},
        }

    def _baseline(self, transactions: list[dict[str, Any]], category_baselines: dict[str, float], recurrence: list[MerchantRecurrence]) -> BehaviorBaseline:
        amounts = [float(tx["expense_amount"]) for tx in transactions]
        unique_days = sorted({tx["date"] for tx in transactions})
        days_count = max(1, len(unique_days))
        weekend_spend = sum(float(tx["expense_amount"]) for tx in transactions if tx["date"].weekday() >= 5)
        total = sum(amounts)
        merchant_counts = Counter(str(tx["description"]).upper() for tx in transactions)
        hour_counts = Counter(int(tx["hour"]) for tx in transactions)
        return BehaviorBaseline(
            average_transaction_amount=round(mean(amounts), 2) if amounts else 0.0,
            median_transaction_amount=round(median(amounts), 2) if amounts else 0.0,
            average_daily_spend=round(total / days_count, 2),
            average_weekly_spend=round((total / days_count) * 7.0, 2),
            usual_active_hours=[hour for hour, _ in hour_counts.most_common(3)],
            weekend_spend_ratio=round((weekend_spend / total), 4) if total > 0 else 0.0,
            top_merchants=[merchant for merchant, _ in merchant_counts.most_common(5)],
            recurring_merchants=[item.merchant for item in recurrence if item.transaction_count >= 2][:5],
            category_baselines=category_baselines,
        )

    def _category_drift(self, current_totals: dict[str, float], baseline_totals: dict[str, float]) -> dict[str, Any]:
        categories = sorted(set(current_totals.keys()) | set(baseline_totals.keys()))
        drifts: list[CategoryDrift] = []
        magnitude_values: list[float] = []
        for category in categories:
            baseline = float(baseline_totals.get(category, 0.0))
            current = float(current_totals.get(category, 0.0))
            if baseline <= 0 and current <= 0:
                drift_pct = 0.0
            elif baseline <= 0:
                drift_pct = 100.0
            else:
                drift_pct = ((current - baseline) / baseline) * 100.0
            severity = self._drift_severity(abs(drift_pct))
            magnitude_values.append(min(100.0, abs(drift_pct)))
            drifts.append(
                CategoryDrift(
                    category=category,
                    baseline_amount=round(baseline, 2),
                    current_amount=round(current, 2),
                    drift_percentage=round(drift_pct, 2),
                    severity=severity,
                )
            )
        score = round(mean(magnitude_values), 2) if magnitude_values else 0.0
        score = max(0.0, min(100.0, score))
        return {"drifts": drifts, "drift_score": score, "drift_severity": self._overall_drift_severity(score)}

    def _merchant_recurrence(self, transactions: list[dict[str, Any]]) -> list[MerchantRecurrence]:
        by_merchant: dict[str, list[date]] = defaultdict(list)
        for tx in transactions:
            by_merchant[str(tx["description"]).upper()].append(tx["date"])
        result: list[MerchantRecurrence] = []
        for merchant, dates in by_merchant.items():
            dates = sorted(dates)
            count = len(dates)
            if count >= 2:
                intervals = [(dates[i] - dates[i - 1]).days for i in range(1, count)]
                avg_interval = mean(intervals)
                interval_std = pstdev(intervals) if len(intervals) > 1 else 0.0
                regularity = 1.0 / (1.0 + interval_std)
                frequency = min(1.0, count / 8.0)
                confidence = max(0.0, min(1.0, regularity * frequency))
                expected = dates[-1] + timedelta(days=max(1, int(round(avg_interval))))
                recurrence_type = self._recurrence_type(avg_interval)
                result.append(
                    MerchantRecurrence(
                        merchant=merchant,
                        transaction_count=count,
                        average_interval_days=round(avg_interval, 2),
                        recurrence_confidence=round(confidence, 4),
                        expected_next_date=expected.isoformat(),
                        recurrence_type=recurrence_type,
                    )
                )
            else:
                result.append(
                    MerchantRecurrence(
                        merchant=merchant,
                        transaction_count=count,
                        average_interval_days=0.0,
                        recurrence_confidence=0.0,
                        expected_next_date=None,
                        recurrence_type="irregular",
                    )
                )
        return sorted(result, key=lambda item: item.recurrence_confidence, reverse=True)[:15]

    def _anomaly_events(
        self,
        transactions: list[dict[str, Any]],
        windows: dict[str, float],
        category_drifts: list[CategoryDrift],
        baseline: BehaviorBaseline,
        recurrence: list[MerchantRecurrence],
    ) -> list[BehaviorAnomalyEvent]:
        events: list[BehaviorAnomalyEvent] = []
        high_drift = [d for d in category_drifts if d.severity in {"High", "Critical"}]
        if high_drift:
            max_drift = max(high_drift, key=lambda d: abs(d.drift_percentage))
            events.append(
                BehaviorAnomalyEvent(
                    event_type="category_spend_drift",
                    severity=max_drift.severity,
                    confidence=min(1.0, abs(max_drift.drift_percentage) / 100.0),
                    evidence={"category": max_drift.category, "drift_percentage": max_drift.drift_percentage},
                    recommendation_hint=f"Review {max_drift.category} budget and set a tighter spending cap.",
                )
            )
        if baseline.weekend_spend_ratio > 0.45:
            events.append(
                BehaviorAnomalyEvent(
                    event_type="weekend_spending_drift",
                    severity="Medium" if baseline.weekend_spend_ratio < 0.6 else "High",
                    confidence=min(1.0, baseline.weekend_spend_ratio),
                    evidence={"weekend_spend_ratio": baseline.weekend_spend_ratio},
                    recommendation_hint="Cap discretionary weekend spending with a fixed envelope.",
                )
            )
        if abs(windows["spend_velocity_7d_vs_30d"]) > 0.35:
            velocity = abs(windows["spend_velocity_7d_vs_30d"])
            events.append(
                BehaviorAnomalyEvent(
                    event_type="spending_velocity_spike",
                    severity="High" if velocity > 0.8 else "Medium",
                    confidence=min(1.0, velocity),
                    evidence={"spend_velocity_7d_vs_30d": round(windows["spend_velocity_7d_vs_30d"], 4)},
                    recommendation_hint="Slow near-term spend and re-check recurring commitments.",
                )
            )
        high_value = [tx for tx in transactions if float(tx["expense_amount"]) >= self.HIGH_VALUE_THRESHOLD]
        if high_value:
            largest = max(high_value, key=lambda tx: float(tx["expense_amount"]))
            events.append(
                BehaviorAnomalyEvent(
                    event_type="high_value_transaction",
                    severity="High",
                    confidence=0.9,
                    evidence={"amount": largest["expense_amount"], "merchant": largest["description"], "date": largest["date"].isoformat()},
                    recommendation_hint="Verify this high-value spend aligns with your monthly plan.",
                )
            )
        unusual_hours = [tx for tx in transactions if int(tx["hour"]) < 6 or int(tx["hour"]) > 23]
        if unusual_hours and len(unusual_hours) / max(1, len(transactions)) > 0.2:
            ratio = len(unusual_hours) / max(1, len(transactions))
            events.append(
                BehaviorAnomalyEvent(
                    event_type="unusual_time_activity",
                    severity="Medium",
                    confidence=min(1.0, ratio + 0.2),
                    evidence={"unusual_transaction_count": len(unusual_hours), "ratio": round(ratio, 4)},
                    recommendation_hint="Review late-night transactions for accidental or impulsive spends.",
                )
            )
        frequent = [item for item in recurrence if item.transaction_count >= 3 and item.recurrence_confidence < 0.5]
        if frequent:
            top = frequent[0]
            events.append(
                BehaviorAnomalyEvent(
                    event_type="merchant_frequency_spike",
                    severity="Medium",
                    confidence=min(1.0, top.transaction_count / 10.0),
                    evidence={"merchant": top.merchant, "transaction_count": top.transaction_count},
                    recommendation_hint="Investigate repeated merchant charges for hidden subscriptions.",
                )
            )
        return events

    def _trend_timeline(self, transactions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        daily: dict[str, float] = defaultdict(float)
        for tx in transactions:
            daily[tx["date"].isoformat()] += float(tx["expense_amount"])
        return [{"date": k, "amount": round(v, 2)} for k, v in sorted(daily.items())]

    def _anomaly_score(self, anomalies: list[BehaviorAnomalyEvent]) -> float:
        if not anomalies:
            return 0.0
        return min(1.0, mean(event.confidence for event in anomalies))

    @staticmethod
    def _parse_datetime(value: Any) -> datetime:
        raw = str(value).strip()
        if not raw:
            raise ValueError("missing transaction date")
        try:
            if len(raw) == 10:
                parsed = datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=UTC)
            else:
                parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=UTC)
                parsed = parsed.astimezone(UTC)
            return parsed
        except ValueError as exc:
            raise ValueError(f"invalid date '{raw}'") from exc

    @staticmethod
    def _drift_severity(abs_drift_pct: float) -> str:
        if abs_drift_pct < 15:
            return "Low"
        if abs_drift_pct < 40:
            return "Medium"
        if abs_drift_pct < 80:
            return "High"
        return "Critical"

    @staticmethod
    def _overall_drift_severity(score: float) -> str:
        if score < 5:
            return "Stable"
        if score < 20:
            return "Low"
        if score < 45:
            return "Medium"
        if score < 70:
            return "High"
        return "Critical"

    @staticmethod
    def _recurrence_type(avg_interval: float) -> str:
        if avg_interval <= 10:
            return "weekly"
        if avg_interval <= 40:
            return "monthly"
        return "irregular"
