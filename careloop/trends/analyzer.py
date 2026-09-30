"""
Trend Analyzer (M4)
Computes baseline, delta, 3-day rolling mean, 7-day slope, streaks, adherence %, etc.
"""
from datetime import date
from typing import Any

from careloop.models.data_models import TrendFinding


def _slope(series: list[tuple[date, float]]) -> float | None:
    """Compute least-squares slope for a series of (date, value) pairs."""
    if len(series) < 2:
        return None
    n = len(series)
    xs = list(range(n))
    ys = [v for _, v in series]
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    den = sum((x - mean_x) ** 2 for x in xs)
    if den == 0:
        return 0.0
    return num / den


def _rolling_mean(values: list[float], window: int = 3) -> float | None:
    if not values:
        return None
    recent = values[-window:]
    return sum(recent) / len(recent)


class TrendAnalyzer:
    """
    Analyzes trends from a list of daily slot values.
    All missing days kept as gaps (None), not interpolated.
    """

    def compute_metric(
        self,
        metric: str,
        series_data: list[tuple[date, float | None]],
        baseline: float | None = None,
        window_days: int = 7,
        tolerance: float = 0.05,
        evidence_ids: list[str] | None = None,
    ) -> TrendFinding:
        clean = [(d, v) for d, v in series_data if v is not None]

        if len(clean) < 2:
            return TrendFinding(
                metric=metric,
                window_days=window_days,
                direction="insufficient_data",
                baseline=baseline,
                latest=clean[-1][1] if clean else None,
                delta=None,
                series=series_data,
                evidence_ids=evidence_ids or [],
            )

        values = [v for _, v in clean]
        computed_baseline = baseline if baseline is not None else values[0]
        latest = values[-1]
        delta = latest - computed_baseline

        # 7-day slope
        recent = clean[-window_days:]
        slope = _slope(recent)

        # Direction
        if slope is None:
            direction = "stable"
        elif slope > tolerance:
            direction = "worsening"
        elif slope < -tolerance:
            direction = "improving"
        else:
            direction = "stable"

        # Special cases: for beneficial metrics (sleep, activity, mood) invert direction
        beneficial = ["sleep_hours", "activity_minutes", "mood_wellbeing", "hydration_glasses"]
        if metric in beneficial:
            if direction == "worsening":
                direction = "improving"
            elif direction == "improving":
                direction = "worsening"

        return TrendFinding(
            metric=metric,
            window_days=window_days,
            direction=direction,
            baseline=computed_baseline,
            latest=latest,
            delta=delta,
            series=series_data,
            evidence_ids=evidence_ids or [],
        )

    def compute_adherence(
        self,
        taken_list: list[bool | None],
        window: int = 7,
    ) -> dict[str, Any]:
        """Compute medication adherence metrics."""
        recent = taken_list[-window:]
        taken = sum(1 for v in recent if v is True)
        missed = sum(1 for v in recent if v is False)
        total = len([v for v in recent if v is not None])
        pct = taken / total if total > 0 else None

        # Streak of consecutive missed doses
        streak = 0
        for v in reversed(taken_list):
            if v is False:
                streak += 1
            else:
                break

        return {
            "pct_7d": pct,
            "taken_7d": taken,
            "missed_7d": missed,
            "streak_missed": streak,
        }

    def compute_all(
        self,
        history: list[dict[str, Any]],   # list of {day, slots} dicts
        baselines: dict[str, float],
    ) -> dict[str, Any]:
        """
        Compute trends for all standard metrics from a history of sessions.
        Returns a dict of metric -> TrendFinding or adherence dict.
        """
        results: dict[str, Any] = {}
        metrics = ["weight_kg", "sleep_hours", "activity_minutes", "mood_wellbeing",
                   "hydration_glasses", "glucose_reading"]

        for metric in metrics:
            series = []
            for entry in history:
                d = entry.get("date", date.today())
                val = entry.get("slots", {}).get(metric)
                if isinstance(d, str):
                    try:
                        d = date.fromisoformat(d)
                    except Exception:
                        d = date.today()
                series.append((d, float(val) if val is not None else None))
            baseline = baselines.get(metric)
            results[metric] = self.compute_metric(metric, series, baseline)

        # Medication adherence
        taken_list = [
            entry.get("slots", {}).get("med_taken_today_morning")
            for entry in history
        ]
        results["med_adherence"] = self.compute_adherence(taken_list)

        return results
