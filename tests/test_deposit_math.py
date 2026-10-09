from datetime import date

import pytest

from app.services import deposit_math as dm

# 36.5% a year in 2025 is exactly 0.1% a day: 1000 earns 1 per day
RATE = 0.365
JAN1 = date(2025, 1, 1)


def terms(**kw):
    params = dict(opened=JAN1, amount=1000, rate=RATE, frequency='monthly', capitalize=False)
    params.update(kw)
    return dm.Terms(**params)


@pytest.mark.parametrize('start, months, expected', [
    (date(2024, 1, 31), 1, date(2024, 2, 29)),
    (date(2025, 1, 31), 1, date(2025, 2, 28)),
    (date(2025, 1, 31), 2, date(2025, 3, 31)),
    (date(2025, 11, 15), 3, date(2026, 2, 15)),
    (date(2024, 2, 29), 12, date(2025, 2, 28)),
    (date(2025, 5, 10), 0, date(2025, 5, 10)),
])
def test_add_months(start, months, expected):
    assert dm.add_months(start, months) == expected


@pytest.mark.parametrize('start, end, expected', [
    (date(2025, 1, 1), date(2025, 4, 1), 3),
    (date(2024, 1, 31), date(2024, 2, 29), 1),
    (date(2025, 1, 1), date(2025, 1, 20), None),
    (date(2025, 1, 15), date(2025, 3, 20), None),
    (date(2025, 1, 1), date(2025, 1, 1), None),
])
def test_whole_months(start, end, expected):
    assert dm.whole_months(start, end) == expected


def test_days_in_year():
    assert dm.days_in_year(2024) == 366
    assert dm.days_in_year(2025) == 365
    assert dm.days_in_year(2100) == 365


def test_to_nominal_keeps_nominal_rate():
    assert dm.to_nominal(12, 'nominal', 'monthly') == pytest.approx(0.12)


def test_to_nominal_converts_apy():
    assert dm.to_nominal(12, 'apy', 'monthly') == pytest.approx(12 * (1.12 ** (1 / 12) - 1))
    assert dm.to_nominal(12, 'apy', 'yearly') == pytest.approx(0.12)


def test_apy_and_nominal_match_when_paid_at_the_end():
    assert dm.to_nominal(12, 'apy', 'end') == pytest.approx(0.12)
    assert dm.to_apy(0.12, 'end') == pytest.approx(0.12)


@pytest.mark.parametrize('frequency', ['daily', 'monthly', 'quarterly', 'yearly'])
def test_apy_round_trip(frequency):
    assert dm.to_apy(dm.to_nominal(7.5, 'apy', frequency), frequency) == pytest.approx(0.075)


def test_payout_dates_follow_anniversaries():
    t = terms(opened=date(2024, 1, 31))
    assert list(dm.payout_dates(t, date(2024, 5, 31))) == [
        date(2024, 2, 29), date(2024, 3, 31), date(2024, 4, 30), date(2024, 5, 31)]


def test_payout_dates_last_period_ends_on_end_date():
    t = terms(opened=date(2025, 1, 10), ends=date(2025, 3, 25))
    assert list(dm.payout_dates(t, date(2026, 1, 1))) == [date(2025, 2, 10), date(2025, 3, 10), date(2025, 3, 25)]


def test_payout_dates_end_on_anniversary_is_not_doubled():
    t = terms(opened=date(2025, 1, 10), ends=date(2025, 4, 10))
    assert list(dm.payout_dates(t, date(2026, 1, 1))) == [date(2025, 2, 10), date(2025, 3, 10), date(2025, 4, 10)]


def test_payout_dates_quarterly():
    t = terms(frequency='quarterly')
    assert list(dm.payout_dates(t, date(2025, 12, 31))) == [date(2025, 4, 1), date(2025, 7, 1), date(2025, 10, 1)]


def test_payout_dates_daily():
    t = terms(frequency='daily', ends=date(2025, 1, 4))
    assert list(dm.payout_dates(t, date(2025, 2, 1))) == [date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 4)]


def test_payout_dates_at_the_end():
    t = terms(frequency='end', ends=date(2025, 4, 1))
    assert list(dm.payout_dates(t, date(2025, 3, 31))) == []
    assert list(dm.payout_dates(t, date(2025, 4, 1))) == [date(2025, 4, 1)]


def test_next_payout_date():
    t = terms(ends=date(2025, 3, 15))
    assert dm.next_payout_date(t, JAN1) == date(2025, 2, 1)
    assert dm.next_payout_date(t, date(2025, 2, 1)) == date(2025, 3, 1)
    assert dm.next_payout_date(t, date(2025, 3, 1)) == date(2025, 3, 15)
    assert dm.next_payout_date(t, date(2025, 3, 15)) is None


def test_next_payout_date_daily_and_end():
    daily = terms(frequency='daily', ends=date(2025, 1, 5))
    assert dm.next_payout_date(daily, date(2025, 1, 3)) == date(2025, 1, 4)
    assert dm.next_payout_date(daily, date(2025, 1, 5)) is None
    end = terms(frequency='end', ends=date(2025, 4, 1))
    assert dm.next_payout_date(end, JAN1) == date(2025, 4, 1)
    assert dm.next_payout_date(end, date(2025, 4, 1)) is None


def test_simulate_simple_monthly_payout():
    res = dm.simulate(terms(), date(2025, 2, 1))
    assert res.payouts == [(date(2025, 2, 1), 31.0)]
    assert res.balance == 1000
    assert res.accrued == pytest.approx(0)
    assert res.principal == 1000
    assert not res.matured


def test_simulate_accrues_inside_period():
    res = dm.simulate(terms(), date(2025, 1, 16))
    assert res.payouts == []
    assert res.accrued == pytest.approx(15)
    assert res.interest == pytest.approx(15)


def test_simulate_leap_year_uses_366_days():
    res = dm.simulate(terms(opened=date(2024, 1, 1), rate=0.366), date(2024, 2, 1))
    assert res.payouts == [(date(2024, 2, 1), 31.0)]


def test_simulate_year_boundary_switches_day_count():
    res = dm.simulate(terms(opened=date(2024, 12, 15)), date(2025, 1, 15))
    expected = 1000 * RATE * (16 / 366 + 15 / 365)
    assert res.payouts == [(date(2025, 1, 15), round(expected, 2))]


def test_simulate_capitalization():
    res = dm.simulate(terms(capitalize=True), date(2025, 3, 1))
    (_, first), (_, second) = res.payouts
    assert first == 31.0
    assert second == round((1000 + first) * 0.001 * 28, 2)
    assert res.balance == pytest.approx(1000 + first + second)
    assert res.principal == 1000


def test_simulate_no_capitalization_keeps_balance():
    res = dm.simulate(terms(), date(2025, 3, 1))
    assert [a for _, a in res.payouts] == [31.0, 28.0]
    assert res.balance == 1000


def test_simulate_topup_earns_from_next_day():
    res = dm.simulate(terms(), date(2025, 2, 1), movements=[(date(2025, 1, 11), 1000)])
    # Jan 2..11 on 1000, Jan 12..Feb 1 on 2000
    assert res.payouts == [(date(2025, 2, 1), 52.0)]
    assert res.balance == 2000
    assert res.principal == 2000


def test_simulate_withdrawn_money_earns_through_withdrawal_day():
    res = dm.simulate(terms(), date(2025, 2, 1), movements=[(date(2025, 1, 11), -500)])
    assert res.payouts == [(date(2025, 2, 1), 20.5)]
    assert res.balance == 500
    assert res.principal == 500


def test_simulate_movement_on_opening_day_is_part_of_initial_balance():
    res = dm.simulate(terms(), date(2025, 2, 1), movements=[(JAN1, 1000)])
    assert res.payouts == [(date(2025, 2, 1), 62.0)]


def test_simulate_min_base_ignores_topup_until_next_period():
    t = terms(base='min')
    res = dm.simulate(t, date(2025, 3, 1), movements=[(date(2025, 1, 11), 1000)])
    assert res.payouts == [(date(2025, 2, 1), 31.0), (date(2025, 3, 1), 56.0)]


def test_simulate_min_base_withdrawal_cuts_whole_period():
    res = dm.simulate(terms(base='min'), date(2025, 2, 1), movements=[(date(2025, 1, 25), -500)])
    assert res.payouts == [(date(2025, 2, 1), 15.5)]


def test_simulate_min_base_accrued():
    res = dm.simulate(terms(base='min'), date(2025, 1, 11), movements=[(date(2025, 1, 6), -400)])
    assert res.accrued == pytest.approx(6)


def test_simulate_rate_change_applies_from_its_day():
    res = dm.simulate(terms(), date(2025, 2, 1), rates=[(JAN1, RATE), (date(2025, 1, 11), 0.73)])
    # Jan 2..10 at 0.1%, Jan 11..Feb 1 at 0.2%
    assert res.payouts == [(date(2025, 2, 1), 53.0)]


def test_simulate_stops_at_end_date():
    t = terms(ends=date(2025, 4, 1))
    res = dm.simulate(t, date(2026, 1, 1))
    assert [a for _, a in res.payouts] == [31.0, 28.0, 31.0]
    assert res.matured
    assert not dm.simulate(t, date(2025, 3, 31)).matured


def test_simulate_paid_at_the_end():
    res = dm.simulate(terms(frequency='end', ends=date(2025, 4, 1)), date(2025, 4, 1))
    assert res.payouts == [(date(2025, 4, 1), 90.0)]


def test_simulate_end_frequency_needs_end_date():
    with pytest.raises(ValueError):
        dm.simulate(terms(frequency='end'), date(2025, 4, 1))


def test_simulate_crypto_precision():
    res = dm.simulate(terms(amount=1, rate=0.05, precision=8), date(2025, 2, 1))
    assert res.payouts == [(date(2025, 2, 1), round(0.05 / 365 * 31, 8))]


def test_early_close_keeps_actual_rates():
    res = dm.early_close(terms(), date(2025, 2, 11), paid_out=31.0)
    assert res == {'principal': 1000, 'interest': 41.0, 'paid_out': 31.0, 'holdback': 0.0,
                   'returned': 1010.0, 'days': 41}


def test_early_close_lower_rate_holds_back_overpaid_interest():
    res = dm.early_close(terms(), date(2025, 2, 11), rates=[(JAN1, RATE)], close_rate=0.0365, paid_out=31.0)
    assert res['interest'] == pytest.approx(4.1)
    assert res['holdback'] == pytest.approx(26.9)
    assert res['returned'] == pytest.approx(973.1)


def test_early_close_never_returns_negative():
    res = dm.early_close(terms(), date(2025, 2, 11), close_rate=0.0, paid_out=2000.0)
    assert res['returned'] == 0.0
    assert res['holdback'] == 2000.0
