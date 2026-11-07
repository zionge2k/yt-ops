from datetime import date

from ytops.subscribers import exact_subscribers


def test_exact_subscribers_after_rounding():
    daily = [(date(2026, 11, 2), 5, 1), (date(2026, 11, 3), 3, 0)]
    got = exact_subscribers((date(2026, 11, 1), 998), daily, date(2026, 11, 3), 1000)
    assert got == 1005


def test_baseline_day_counts_and_later_days_ignored():
    # the snapshot is taken ~00:30 UTC, so the baseline day's own gains come after it
    daily = [(date(2026, 10, 31), 70, 0), (date(2026, 11, 1), 50, 0), (date(2026, 11, 2), 5, 1),
             (date(2026, 11, 4), 9, 0)]
    got = exact_subscribers((date(2026, 11, 1), 998), daily, date(2026, 11, 3), 1000)
    assert got == 998 + 50 + 4


def test_under_1000_uses_api_even_with_stale_baseline():
    # baseline from yesterday, Analytics 3 days behind: today's exact API value wins
    daily = [(date(2026, 11, 3), 5, 0)]
    assert exact_subscribers((date(2026, 11, 6), 900), daily, date(2026, 11, 4), 990) == 990


def test_baseline_without_new_days_returns_baseline():
    assert exact_subscribers((date(2026, 11, 1), 998), [], None, 1000) == 998


def test_exact_subscribers_no_baseline_under_1000():
    assert exact_subscribers(None, [], None, 742) == 742


def test_exact_subscribers_no_baseline_over_1000_is_none():
    assert exact_subscribers(None, [], None, 1000) is None
