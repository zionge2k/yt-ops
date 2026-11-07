from datetime import date

from ytops.subscribers import exact_subscribers


def test_exact_subscribers_after_rounding():
    daily = [(date(2026, 11, 2), 5, 1), (date(2026, 11, 3), 3, 0)]
    got = exact_subscribers((date(2026, 11, 1), 998), daily, date(2026, 11, 3), 1000)
    assert got == 1005


def test_baseline_ignores_days_outside_window():
    daily = [(date(2026, 11, 1), 50, 0), (date(2026, 11, 2), 5, 1), (date(2026, 11, 4), 9, 0)]
    got = exact_subscribers((date(2026, 11, 1), 998), daily, date(2026, 11, 3), 1000)
    assert got == 1002


def test_baseline_without_new_days_returns_baseline():
    assert exact_subscribers((date(2026, 11, 1), 998), [], None, 1000) == 998


def test_exact_subscribers_no_baseline_under_1000():
    assert exact_subscribers(None, [], None, 742) == 742


def test_exact_subscribers_no_baseline_over_1000_is_none():
    assert exact_subscribers(None, [], None, 1000) is None
