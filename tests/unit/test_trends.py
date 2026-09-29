"""
Unit tests for Trend Analyzer (M4)
"""
import pytest
from datetime import date
from careloop.trends.analyzer import TrendAnalyzer


@pytest.fixture
def analyzer():
    return TrendAnalyzer()


def make_series(values):
    """Build (date, value) series from a list of values."""
    start = date(2026, 9, 1)
    return [(date(2026, 9, i + 1), v) for i, v in enumerate(values)]


def test_worsening_weight(analyzer):
    series = make_series([70.0, 70.5, 71.0, 71.5, 72.0])
    result = analyzer.compute_metric("weight_kg", series, baseline=70.0)
    assert result.direction == "worsening"
    assert result.delta == pytest.approx(2.0, abs=0.1)


def test_improving_sleep(analyzer):
    series = make_series([4.0, 5.0, 6.0, 7.0])
    result = analyzer.compute_metric("sleep_hours", series, baseline=4.0)
    # Negative slope -> improving for beneficial metric
    assert result.direction in ("improving", "stable")


def test_stable_metric(analyzer):
    series = make_series([7.0, 7.1, 7.0, 6.9, 7.0])
    result = analyzer.compute_metric("sleep_hours", series, baseline=7.0, tolerance=0.5)
    assert result.direction == "stable"


def test_missing_days_preserved(analyzer):
    series = [(date(2026, 9, 1), 70.0), (date(2026, 9, 2), None), (date(2026, 9, 3), 71.0)]
    result = analyzer.compute_metric("weight_kg", series, baseline=70.0)
    # Should still compute with available data
    assert result.metric == "weight_kg"
    assert any(v is None for _, v in result.series)


def test_insufficient_data(analyzer):
    series = make_series([70.0])
    result = analyzer.compute_metric("weight_kg", series, baseline=70.0)
    assert result.direction == "insufficient_data"


def test_adherence_high(analyzer):
    taken = [True] * 6 + [False]
    result = analyzer.compute_adherence(taken)
    assert result["pct_7d"] == pytest.approx(6 / 7, abs=0.01)
    assert result["missed_7d"] == 1


def test_adherence_streak_missed(analyzer):
    taken = [True, True, True, True, False, False, False]
    result = analyzer.compute_adherence(taken)
    assert result["streak_missed"] == 3


def test_baseline_delta(analyzer):
    series = make_series([65.0, 65.5, 66.0, 66.5])
    result = analyzer.compute_metric("weight_kg", series, baseline=65.0)
    assert result.delta == pytest.approx(1.5, abs=0.1)
    assert result.latest == pytest.approx(66.5, abs=0.1)
