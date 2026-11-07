from datetime import date

from ytops import periods


def test_window_and_previous():
    w = periods.window(date(2026, 11, 4), 7)
    assert w == (date(2026, 10, 29), date(2026, 11, 4))
    assert periods.previous(w) == (date(2026, 10, 22), date(2026, 10, 28))


def test_pct_change_none_when_prev_zero():
    assert periods.pct_change(5, 0) is None
    assert periods.pct_change(None, 5) is None
    assert periods.pct_change(5, None) is None
    assert periods.pct_change(110, 100) == 10.0


def test_status_thresholds():
    assert periods.status_of(5.0, 5.0, -5.0) == "green"
    assert periods.status_of(0.0, 5.0, -5.0) == "yellow"
    assert periods.status_of(-6.0, 5.0, -5.0) == "red"
    assert periods.status_of(None, 5.0, -5.0) == "grey"


def test_pct_change_negative_prev():
    assert periods.pct_change(4, -2) == 300.0
    assert periods.pct_change(-4, -2) == -100.0


def test_half_trend_splits_window():
    # first half 1+1, second half 2+2 -> +100%
    assert periods.half_trend([1, 1, 2, 2]) == 100.0
    # odd length: the middle day is dropped ([1] vs [1]) -> flat
    assert periods.half_trend([1, 1, 1]) == 0.0
    # None skipped per half, means compared: first mean 2/1 = 2.0, second mean (1+1)/2 = 1.0 -> -50%
    assert periods.half_trend([2, None, 1, 1]) == -50.0
    assert periods.half_trend([None, None, 1, 1]) is None
    assert periods.half_trend([0, 0, 1, 1]) is None  # first half total 0
    assert periods.half_trend([5]) is None and periods.half_trend([]) is None
    assert periods.half_trend([4, 4, 2, 2]) == -50.0


def test_color_of():
    assert periods.color_of(5.0, 5.0, -5.0) == "red"
    assert periods.color_of(0.0, 5.0, -5.0) == "purple"
    assert periods.color_of(-5.0, 5.0, -5.0) == "blue"
    assert periods.color_of(None, 5.0, -5.0) == "grey"


def test_compare_window_is_at_least_four_weeks():
    w7 = periods.window(date(2026, 11, 4), 7)
    assert periods.compare_window(w7) == (date(2026, 10, 1), date(2026, 10, 28))
    w28 = periods.window(date(2026, 11, 4), 28)
    assert periods.compare_window(w28) == periods.previous(w28)
    w90 = periods.window(date(2026, 11, 4), 90)
    assert periods.compare_window(w90) == periods.previous(w90)


def test_half_trend_flat_odd_window_is_zero():
    assert periods.half_trend([1] * 7) == 0.0
    assert periods.half_trend([1] * 365) == 0.0


def test_half_trend_unequal_valid_days_uses_means():
    # first half [1, None] mean 1.0, second half [1, 1] mean 1.0 -> flat (sums would say +100%)
    assert periods.half_trend([1, None, 1, 1]) == 0.0
