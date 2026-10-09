from datetime import date

import pytest

from app.models.db_session import create_session
from app.models.deposits import Deposit, DepositEvent, DepositNotice
from app.models.portfolios import Portfolio
from app.services import deposit_math as dm
from app.services import deposits
from app.services.deposits import DepositError

# 36.5% a year in 2025 is exactly 0.1% a day: 1000 earns 1 per day
JAN1, JAN11, JAN16 = date(2025, 1, 1), date(2025, 1, 11), date(2025, 1, 16)
FEB1, FEB11, MAR1, APR1, MAY1 = date(2025, 2, 1), date(2025, 2, 11), date(2025, 3, 1), date(2025, 4, 1), date(2025, 5, 1)


def add(portfolio_id, **kw):
    params = dict(kind='fiat', asset='USD', title='Тест', amount=1000, rate=36.5, rate_type='nominal',
                  frequency='monthly', capitalize=False, opened_at=JAN1, today=JAN1)
    params.update(kw)
    return deposits.add_deposit(portfolio_id, **params)


def holdings(portfolio_id):
    with create_session() as session:
        return session.get(Portfolio, portfolio_id).get_dict()


def get_deposit(deposit_id):
    with create_session() as session:
        return session.get(Deposit, deposit_id)


def events(deposit_id, kind=None):
    with create_session() as session:
        q = session.query(DepositEvent).filter(DepositEvent.deposit_id == deposit_id)
        if kind:
            q = q.filter(DepositEvent.kind == kind)
        return q.order_by(DepositEvent.day, DepositEvent.id).all()


def notices(portfolio_id, unread=True):
    with create_session() as session:
        q = session.query(DepositNotice).filter(DepositNotice.portfolio_id == portfolio_id)
        if unread:
            q = q.filter(DepositNotice.acknowledged_at.is_(None))
        return q.order_by(DepositNotice.id).all()


# add_deposit

def test_add_deposit_stores_terms_and_open_event(portfolio):
    dep_id = add(portfolio, asset=' usd ', title='  ', term_months=3)
    dep = get_deposit(dep_id)
    assert dep.asset == 'USD'
    assert dep.title == 'Вклад в USD'
    assert dep.ends_at == APR1
    assert dep.last_settled_at == JAN1
    assert dep.closed_at is None
    (event,) = events(dep_id)
    assert (event.kind, event.day, event.amount, event.rate, event.linked) == ('open', JAN1, 1000, 36.5, False)
    assert holdings(portfolio)['fiat'] == {'USD': 5000}


def test_add_deposit_takes_money_from_holdings(portfolio):
    dep_id = add(portfolio, amount=1200, take_from_holdings=True)
    assert holdings(portfolio)['fiat'] == {'USD': 3800}
    assert events(dep_id)[0].linked


def test_add_deposit_taking_everything_removes_position(portfolio):
    add(portfolio, amount=5000, take_from_holdings=True)
    assert holdings(portfolio)['fiat'] == {}


def test_add_deposit_not_enough_in_portfolio(portfolio):
    with pytest.raises(DepositError, match='В портфеле только'):
        add(portfolio, amount=5000.01, take_from_holdings=True)
    with pytest.raises(DepositError, match='В портфеле только'):
        add(portfolio, asset='EUR', take_from_holdings=True)
    assert holdings(portfolio)['fiat'] == {'USD': 5000}


def test_add_crypto_deposit_rounds_to_8_digits(portfolio):
    dep_id = add(portfolio, kind='crypto', asset='eth', amount=1.123456789, take_from_holdings=True)
    assert get_deposit(dep_id).amount == 1.12345679
    assert holdings(portfolio)['crypto'] == {'ETH': 0.87654321}


def test_title_is_cut_to_120_chars(portfolio):
    assert len(get_deposit(add(portfolio, title='x' * 200)).title) == 120


@pytest.mark.parametrize('override, message', [
    ({'kind': 'stocks'}, 'Неизвестный тип вклада'),
    ({'amount': 0}, 'Сумма должна быть больше нуля'),
    ({'amount': None}, 'Сумма должна быть больше нуля'),
    ({'rate': -1}, 'Ставка должна быть от 0 до 1000%'),
    ({'rate': 1001}, 'Ставка должна быть от 0 до 1000%'),
    ({'rate': None}, 'Ставка должна быть от 0 до 1000%'),
    ({'rate_type': 'effective'}, 'Неизвестный тип ставки'),
    ({'frequency': 'weekly'}, 'Неизвестная частота'),
    ({'base': 'max'}, 'Неизвестный способ начисления'),
    ({'opened_at': date(2025, 1, 2)}, 'Дата открытия не может быть в будущем'),
    ({'ends_at': JAN1}, 'Дата окончания должна быть позже даты открытия'),
    ({'frequency': 'end'}, 'укажите срок вклада'),
    ({'opened_at': date(2024, 1, 1), 'term_months': 12}, 'Срок этого вклада уже закончился'),
    ({'asset': 'XYZ'}, 'Такой валюты нет'),
    ({'kind': 'crypto', 'asset': 'XYZ'}, 'Такой монеты нет'),
])
def test_add_deposit_validation(portfolio, override, message):
    with pytest.raises(DepositError, match=message):
        add(portfolio, **override)


def test_add_deposit_unknown_portfolio(db):
    with pytest.raises(DepositError, match='Портфель не найден'):
        add(12345)


def test_rate_zero_and_max_are_allowed(portfolio):
    add(portfolio, rate=0)
    add(portfolio, rate=1000)


def test_opened_in_the_past_records_payouts_without_moving_money(portfolio):
    dep_id = add(portfolio, opened_at=JAN1, today=MAR1, take_from_holdings=True)
    payouts = [(e.day, e.amount, e.linked) for e in events(dep_id, 'payout')]
    assert payouts == [(FEB1, 31.0, False), (MAR1, 28.0, False)]
    assert holdings(portfolio)['fiat'] == {'USD': 4000}
    assert get_deposit(dep_id).last_settled_at == MAR1
    assert deposits.settle_portfolio(portfolio, today=MAR1) == 0
    assert notices(portfolio) == []


def test_capitalized_deposit_opened_in_the_past_has_no_payout_events(portfolio):
    dep_id = add(portfolio, capitalize=True, today=MAR1)
    assert events(dep_id, 'payout') == []


# settle_portfolio

def test_settle_moves_payout_to_portfolio_with_notice(portfolio):
    dep_id = add(portfolio, take_from_holdings=True)
    assert deposits.settle_portfolio(portfolio, today=FEB1) == 1
    assert holdings(portfolio)['fiat'] == {'USD': 4031}
    assert get_deposit(dep_id).last_settled_at == FEB1
    (payout,) = events(dep_id, 'payout')
    assert (payout.day, payout.amount, payout.linked) == (FEB1, 31.0, True)
    (notice,) = notices(portfolio)
    assert (notice.kind, notice.section, notice.asset, notice.amount) == ('payout', 'fiat', 'USD', 31.0)
    assert (notice.period_from, notice.period_to, notice.payouts) == (date(2025, 1, 2), FEB1, 1)


def test_settle_twice_pays_once(portfolio):
    add(portfolio, take_from_holdings=True)
    deposits.settle_portfolio(portfolio, today=FEB1)
    assert deposits.settle_portfolio(portfolio, today=FEB1) == 0
    assert holdings(portfolio)['fiat'] == {'USD': 4031}
    assert len(notices(portfolio)) == 1


def test_settle_inside_period_only_moves_date(portfolio):
    dep_id = add(portfolio, take_from_holdings=True)
    assert deposits.settle_portfolio(portfolio, today=JAN16) == 1
    assert get_deposit(dep_id).last_settled_at == JAN16
    assert holdings(portfolio)['fiat'] == {'USD': 4000}
    assert notices(portfolio) == []


def test_unread_notice_accumulates_payouts(portfolio):
    add(portfolio, take_from_holdings=True)
    deposits.settle_portfolio(portfolio, today=FEB1)
    deposits.settle_portfolio(portfolio, today=MAR1)
    (notice,) = notices(portfolio)
    assert (notice.amount, notice.payouts, notice.period_from, notice.period_to) == (59.0, 2, date(2025, 1, 2), MAR1)
    assert holdings(portfolio)['fiat'] == {'USD': 4059}


def test_acknowledged_notice_starts_a_new_one(portfolio):
    add(portfolio)
    deposits.settle_portfolio(portfolio, today=FEB1)
    assert deposits.acknowledge_notice(portfolio, notices(portfolio)[0].id)
    deposits.settle_portfolio(portfolio, today=MAR1)
    (notice,) = notices(portfolio)
    assert (notice.amount, notice.payouts, notice.period_from, notice.period_to) == (28.0, 1, date(2025, 2, 2), MAR1)


def test_several_periods_settled_at_once(portfolio):
    add(portfolio)
    deposits.settle_portfolio(portfolio, today=APR1)
    (notice,) = notices(portfolio)
    assert (notice.amount, notice.payouts, notice.period_from, notice.period_to) == (90.0, 3, date(2025, 1, 2), APR1)


def test_daily_payouts_make_one_notice(portfolio):
    add(portfolio, frequency='daily')
    deposits.settle_portfolio(portfolio, today=JAN11)
    (notice,) = notices(portfolio)
    assert (notice.amount, notice.payouts) == (10.0, 10)
    assert holdings(portfolio)['fiat'] == {'USD': 5010}


def test_capitalized_interest_stays_on_deposit(portfolio):
    dep_id = add(portfolio, capitalize=True, take_from_holdings=True)
    deposits.settle_portfolio(portfolio, today=MAR1)
    assert holdings(portfolio)['fiat'] == {'USD': 4000}
    assert notices(portfolio) == []
    assert events(dep_id, 'payout') == []
    (info,) = deposits.portfolio_deposits(portfolio, today=MAR1)
    assert info['balance'] == pytest.approx(1031 + 28.87)


def test_matured_deposit_returns_money(portfolio):
    dep_id = add(portfolio, term_months=3, take_from_holdings=True)
    assert deposits.settle_portfolio(portfolio, today=MAY1) == 1
    # Feb 1 and Mar 1 payouts, then the body with the last payout
    assert holdings(portfolio)['fiat'] == {'USD': 4000 + 59 + 1031}
    dep = get_deposit(dep_id)
    assert (dep.closed_at, dep.close_reason, dep.returned, dep.last_settled_at) == (APR1, 'matured', 1031, APR1)
    payout, matured = notices(portfolio)
    assert (payout.kind, payout.amount, payout.payouts, payout.period_to) == ('payout', 59.0, 2, MAR1)
    assert (matured.kind, matured.amount, matured.interest, matured.principal) == ('matured', 1031, 90.0, 1000)
    assert (matured.period_from, matured.period_to) == (JAN1, APR1)
    (close,) = events(dep_id, 'close')
    assert (close.day, close.amount, close.linked) == (APR1, 1031, True)
    assert deposits.settle_portfolio(portfolio, today=date(2025, 6, 1)) == 0


def test_matured_on_its_end_date(portfolio):
    dep_id = add(portfolio, term_months=3)
    deposits.settle_portfolio(portfolio, today=MAR1)
    deposits.settle_portfolio(portfolio, today=APR1)
    assert get_deposit(dep_id).close_reason == 'matured'
    assert holdings(portfolio)['fiat'] == {'USD': 5000 + 90 + 1000}


def test_matured_capitalized_deposit(portfolio):
    add(portfolio, term_months=3, capitalize=True, take_from_holdings=True)
    deposits.settle_portfolio(portfolio, today=MAY1)
    (matured,) = notices(portfolio)
    # 31.00, then 28.87 on 1031.00, then 32.86 on 1059.87
    assert matured.amount == pytest.approx(1092.73)
    assert matured.interest == pytest.approx(92.73)
    assert holdings(portfolio)['fiat']['USD'] == pytest.approx(4000 + 1092.73)


def test_paid_at_the_end(portfolio):
    add(portfolio, frequency='end', term_months=3, take_from_holdings=True)
    deposits.settle_portfolio(portfolio, today=MAR1)
    assert notices(portfolio) == []
    deposits.settle_portfolio(portfolio, today=APR1)
    (matured,) = notices(portfolio)
    assert (matured.kind, matured.amount, matured.interest) == ('matured', 1090, 90.0)
    assert holdings(portfolio)['fiat'] == {'USD': 5090}


def test_settle_only_touches_own_portfolio(portfolio):
    with create_session() as session:
        other = Portfolio(contains={'stocks': {}, 'crypto': {}, 'fiat': {}}, isprivate=False)
        session.add(other)
        session.commit()
        other_id = other.id
    add(other_id)
    assert deposits.settle_portfolio(portfolio, today=FEB1) == 0
    assert deposits.settle_portfolio(other_id, today=FEB1) == 1
    assert holdings(portfolio)['fiat'] == {'USD': 5000}
    assert holdings(other_id)['fiat'] == {'USD': 31}


def test_settle_loses_race_to_another_worker(portfolio, monkeypatch):
    dep_id = add(portfolio, take_from_holdings=True)
    simulate = dm.simulate

    def racing(*args, **kwargs):
        with create_session() as session:
            session.query(Deposit).filter(Deposit.id == dep_id).update({'last_settled_at': FEB1})
            session.commit()
        return simulate(*args, **kwargs)

    monkeypatch.setattr(dm, 'simulate', racing)
    assert deposits._settle_one(dep_id, FEB1) is False
    assert holdings(portfolio)['fiat'] == {'USD': 4000}
    assert events(dep_id, 'payout') == []
    assert notices(portfolio) == []


# top_up / withdraw / change_rate

def test_top_up(portfolio):
    dep_id = add(portfolio)
    deposits.top_up(portfolio, dep_id, 1000, take_from_holdings=True, today=JAN11)
    assert holdings(portfolio)['fiat'] == {'USD': 4000}
    (event,) = events(dep_id, 'topup')
    assert (event.day, event.amount, event.linked) == (JAN11, 1000, True)
    deposits.settle_portfolio(portfolio, today=FEB1)
    assert notices(portfolio)[0].amount == 52.0


def test_top_up_without_portfolio_money(portfolio):
    dep_id = add(portfolio)
    deposits.top_up(portfolio, dep_id, 10_000, today=JAN11)
    assert holdings(portfolio)['fiat'] == {'USD': 5000}
    assert not events(dep_id, 'topup')[0].linked


def test_top_up_not_enough_in_portfolio(portfolio):
    dep_id = add(portfolio)
    with pytest.raises(DepositError, match='В портфеле только 5 000 USD'):
        deposits.top_up(portfolio, dep_id, 5000.5, take_from_holdings=True, today=JAN11)
    assert events(dep_id, 'topup') == []


def test_top_up_settles_due_payouts_first(portfolio):
    dep_id = add(portfolio)
    deposits.top_up(portfolio, dep_id, 100, today=FEB11)
    assert holdings(portfolio)['fiat'] == {'USD': 5031}
    assert get_deposit(dep_id).last_settled_at == FEB11


@pytest.mark.parametrize('kw, message', [
    ({'amount': 0}, 'Сумма должна быть больше нуля'),
    ({'amount': -5}, 'Сумма должна быть больше нуля'),
    ({'day': date(2025, 1, 12)}, 'Дата не может быть в будущем'),
])
def test_top_up_validation(portfolio, kw, message):
    dep_id = add(portfolio)
    with pytest.raises(DepositError, match=message):
        deposits.top_up(portfolio, dep_id, **{'amount': 100, 'today': JAN11, **kw})


def test_operations_before_last_settlement_are_rejected(portfolio):
    dep_id = add(portfolio)
    deposits.settle_portfolio(portfolio, today=FEB1)
    with pytest.raises(DepositError, match='нельзя провести раньше 01.02.2025'):
        deposits.top_up(portfolio, dep_id, 100, day=JAN16, today=FEB1)
    with pytest.raises(DepositError, match='нельзя провести раньше'):
        deposits.withdraw(portfolio, dep_id, 100, day=JAN16, today=FEB1)
    with pytest.raises(DepositError, match='нельзя провести раньше'):
        deposits.change_rate(portfolio, dep_id, 10, day=JAN16, today=FEB1)
    with pytest.raises(DepositError, match='нельзя провести раньше'):
        deposits.close_early(portfolio, dep_id, day=JAN16, today=FEB1)


def test_backdated_operation_after_last_settlement(portfolio):
    dep_id = add(portfolio)
    deposits.top_up(portfolio, dep_id, 1000, day=JAN11, today=JAN11)
    deposits.withdraw(portfolio, dep_id, 500, day=JAN11, today=JAN11)
    assert [e.kind for e in events(dep_id)] == ['open', 'topup', 'withdraw']


def test_operations_on_unknown_or_foreign_deposit(portfolio):
    dep_id = add(portfolio)
    for pid, did in ((portfolio + 1, dep_id), (portfolio, dep_id + 1)):
        with pytest.raises(DepositError, match='Вклад не найден'):
            deposits.top_up(pid, did, 100, today=JAN11)
        with pytest.raises(DepositError, match='Вклад не найден'):
            deposits.withdraw(pid, did, 100, today=JAN11)
        with pytest.raises(DepositError, match='Вклад не найден'):
            deposits.change_rate(pid, did, 10, today=JAN11)
        with pytest.raises(DepositError, match='Вклад не найден'):
            deposits.close_preview(pid, did, today=JAN11)
        with pytest.raises(DepositError, match='Вклад не найден'):
            deposits.close_early(pid, did, today=JAN11)


def test_operations_after_end_date_are_rejected(portfolio):
    dep_id = add(portfolio, term_months=3)
    deposits.settle_portfolio(portfolio, today=APR1)
    with pytest.raises(DepositError, match='Вклад уже закрыт'):
        deposits.top_up(portfolio, dep_id, 100, today=APR1)


def test_withdraw_returns_money_to_portfolio(portfolio):
    dep_id = add(portfolio, take_from_holdings=True)
    deposits.withdraw(portfolio, dep_id, 500, return_to_holdings=True, today=JAN11)
    assert holdings(portfolio)['fiat'] == {'USD': 4500}
    (event,) = events(dep_id, 'withdraw')
    assert (event.day, event.amount, event.linked) == (JAN11, 500, True)
    deposits.settle_portfolio(portfolio, today=FEB1)
    assert notices(portfolio)[0].amount == 20.5


def test_withdraw_more_than_balance(portfolio):
    dep_id = add(portfolio)
    with pytest.raises(DepositError, match='На вкладе только 1 000 USD'):
        deposits.withdraw(portfolio, dep_id, 1000.01, today=JAN11)


def test_withdraw_everything_keeps_deposit_open(portfolio):
    dep_id = add(portfolio, capitalize=True)
    deposits.settle_portfolio(portfolio, today=FEB1)
    deposits.withdraw(portfolio, dep_id, 1031, today=FEB1)
    assert get_deposit(dep_id).closed_at is None
    (info,) = deposits.portfolio_deposits(portfolio, today=FEB11)
    assert info['balance'] == pytest.approx(0)
    assert info['accrued'] == pytest.approx(0)


def test_withdraw_validation(portfolio):
    dep_id = add(portfolio)
    with pytest.raises(DepositError, match='Сумма должна быть больше нуля'):
        deposits.withdraw(portfolio, dep_id, 0, today=JAN11)


def test_change_rate(portfolio):
    dep_id = add(portfolio)
    deposits.change_rate(portfolio, dep_id, 73, today=JAN11)
    dep = get_deposit(dep_id)
    assert (dep.rate, dep.rate_type) == (73, 'nominal')
    (event,) = events(dep_id, 'rate')
    assert (event.day, event.rate, event.rate_type) == (JAN11, 73, 'nominal')
    deposits.settle_portfolio(portfolio, today=FEB1)
    assert notices(portfolio)[0].amount == 53.0


def test_change_rate_to_apy(portfolio):
    dep_id = add(portfolio)
    deposits.change_rate(portfolio, dep_id, 12, rate_type='apy', today=JAN11)
    (info,) = deposits.portfolio_deposits(portfolio, today=JAN11)
    assert info['nominal'] == pytest.approx(12 * (1.12 ** (1 / 12) - 1))


@pytest.mark.parametrize('rate, rate_type', [(-1, 'nominal'), (1001, 'nominal'), (None, 'nominal'), (5, 'x')])
def test_change_rate_validation(portfolio, rate, rate_type):
    dep_id = add(portfolio)
    with pytest.raises(DepositError):
        deposits.change_rate(portfolio, dep_id, rate, rate_type=rate_type, today=JAN11)
    assert events(dep_id, 'rate') == []


# close_preview / close_early

def test_close_preview_counts_unsettled_payouts(portfolio):
    dep_id = add(portfolio)
    res = deposits.close_preview(portfolio, dep_id, today=FEB11)
    assert res == {'principal': 1000, 'interest': 41.0, 'paid_out': 31.0, 'holdback': 0.0,
                   'returned': 1010.0, 'days': 41, 'asset': 'USD'}
    # Nothing has changed
    assert get_deposit(dep_id).last_settled_at == JAN1
    assert holdings(portfolio)['fiat'] == {'USD': 5000}


def test_close_preview_with_lower_rate(portfolio):
    dep_id = add(portfolio)
    res = deposits.close_preview(portfolio, dep_id, close_rate=3.65, today=FEB11)
    assert res['interest'] == pytest.approx(4.1)
    assert res['holdback'] == pytest.approx(26.9)
    assert res['returned'] == pytest.approx(973.1)


def test_close_preview_validation(portfolio):
    dep_id = add(portfolio)
    with pytest.raises(DepositError, match='Дата не может быть в будущем'):
        deposits.close_preview(portfolio, dep_id, day=FEB1, today=JAN11)
    with pytest.raises(DepositError, match='Ставка'):
        deposits.close_preview(portfolio, dep_id, close_rate=-1, today=JAN11)


def test_close_early_at_deposit_rate(portfolio):
    dep_id = add(portfolio, take_from_holdings=True)
    res = deposits.close_early(portfolio, dep_id, today=FEB11)
    assert res['returned'] == 1010.0
    # Feb 1 payout from settlement, then the body with the rest of the interest
    assert holdings(portfolio)['fiat'] == {'USD': 4000 + 31 + 1010}
    dep = get_deposit(dep_id)
    assert (dep.closed_at, dep.close_reason, dep.returned) == (FEB11, 'early', 1010.0)
    (close,) = events(dep_id, 'close')
    assert (close.day, close.amount, close.linked) == (FEB11, 1010.0, True)


def test_close_early_holds_back_overpaid_interest(portfolio):
    dep_id = add(portfolio, take_from_holdings=True)
    res = deposits.close_early(portfolio, dep_id, close_rate=3.65, today=FEB11)
    assert res['holdback'] == pytest.approx(26.9)
    assert holdings(portfolio)['fiat']['USD'] == pytest.approx(4000 + 31 + 973.1)


def test_close_early_capitalized(portfolio):
    dep_id = add(portfolio, capitalize=True, take_from_holdings=True)
    res = deposits.close_early(portfolio, dep_id, today=FEB11)
    # 1031 after Feb 1, then 10 days on it
    assert res['paid_out'] == 0
    assert res['returned'] == pytest.approx(round(1031 + 10.31, 2))
    assert holdings(portfolio)['fiat']['USD'] == pytest.approx(4000 + 1041.31)


def test_closed_deposit_rejects_operations(portfolio):
    dep_id = add(portfolio)
    deposits.close_early(portfolio, dep_id, today=JAN11)
    with pytest.raises(DepositError, match='Вклад уже закрыт'):
        deposits.close_early(portfolio, dep_id, today=JAN11)
    with pytest.raises(DepositError, match='Вклад уже закрыт'):
        deposits.withdraw(portfolio, dep_id, 1, today=JAN11)
    with pytest.raises(DepositError, match='Вклад уже закрыт'):
        deposits.close_preview(portfolio, dep_id, today=JAN11)
    assert deposits.settle_portfolio(portfolio, today=FEB1) == 0


# Notices, renewal, portfolio view

def test_acknowledge_notice(portfolio):
    add(portfolio)
    deposits.settle_portfolio(portfolio, today=FEB1)
    notice_id = notices(portfolio)[0].id
    assert not deposits.acknowledge_notice(portfolio + 1, notice_id)
    assert not deposits.acknowledge_notice(portfolio, notice_id + 1)
    assert deposits.acknowledge_notice(portfolio, notice_id)
    assert not deposits.acknowledge_notice(portfolio, notice_id)
    assert notices(portfolio) == []


def test_pending_credits(portfolio):
    add(portfolio, term_months=3)
    add(portfolio, kind='crypto', asset='ETH', amount=1, rate=3.65)
    deposits.settle_portfolio(portfolio, today=MAY1)
    credits = deposits.pending_credits(portfolio)
    assert credits[('fiat', 'USD')] == 59 + 1031
    assert credits[('crypto', 'ETH')] == pytest.approx(round(0.0001 * 120, 8))
    for notice in notices(portfolio):
        deposits.acknowledge_notice(portfolio, notice.id)
    assert deposits.pending_credits(portfolio) == {}


def test_renew_prefill(portfolio):
    dep_id = add(portfolio, title='Долларовый', term_months=3, capitalize=True, base='min')
    assert deposits.renew_prefill(portfolio, dep_id) is None
    deposits.settle_portfolio(portfolio, today=MAY1)
    prefill = deposits.renew_prefill(portfolio, dep_id)
    returned = get_deposit(dep_id).returned
    assert prefill == {
        'kind': 'fiat', 'asset': 'USD', 'title': 'Долларовый', 'amount': returned,
        'rate': 36.5, 'rate_type': 'nominal', 'frequency': 'monthly', 'capitalize': True, 'base': 'min',
        'opened_at': APR1, 'term_months': 3, 'ends_at': None, 'take_from_holdings': True,
    }
    assert deposits.renew_prefill(portfolio + 1, dep_id) is None

    new_id = deposits.add_deposit(portfolio, **prefill, today=MAY1)
    new = get_deposit(new_id)
    assert (new.opened_at, new.ends_at, new.amount) == (APR1, date(2025, 7, 1), returned)
    assert holdings(portfolio)['fiat']['USD'] == pytest.approx(5000)


def test_renew_prefill_odd_term_keeps_length(portfolio):
    dep_id = add(portfolio, ends_at=date(2025, 1, 20))
    deposits.settle_portfolio(portfolio, today=date(2025, 1, 20))
    prefill = deposits.renew_prefill(portfolio, dep_id)
    assert prefill['term_months'] is None
    assert prefill['ends_at'] == date(2025, 2, 8)


def test_renew_prefill_not_for_early_close(portfolio):
    dep_id = add(portfolio, term_months=3)
    deposits.close_early(portfolio, dep_id, today=JAN11)
    assert deposits.renew_prefill(portfolio, dep_id) is None


def test_portfolio_deposits_card_numbers(portfolio):
    dep_id = add(portfolio, term_months=3)
    (info,) = deposits.portfolio_deposits(portfolio, today=JAN16)
    assert info['id'] == dep_id
    assert info['balance'] == 1000
    assert info['accrued'] == pytest.approx(15)
    assert info['earned'] == pytest.approx(15)
    assert info['paid_out'] == 0
    assert info['nominal'] == pytest.approx(0.365)
    assert info['apy'] == pytest.approx(0.365)
    assert info['next_payout'] == {'date': FEB1, 'amount': 31.0}
    assert info['forecast']['date'] == APR1
    assert info['forecast']['balance'] == pytest.approx(1000)
    assert info['forecast']['interest'] == pytest.approx(90)
    assert info['forecast']['income'] == pytest.approx(75)
    assert info['progress'] == pytest.approx(15 / 90)
    assert info['days_left'] == 75
    assert info['notices'] == []


def test_portfolio_deposits_open_ended_capitalized(portfolio):
    add(portfolio, capitalize=True, rate=12, rate_type='apy')
    (info,) = deposits.portfolio_deposits(portfolio, today=JAN16)
    assert info['apy'] == pytest.approx(0.12)
    assert info['forecast']['date'] == date(2026, 1, 16)
    assert info['progress'] is None
    assert info['days_left'] is None


def test_portfolio_deposits_order_and_closed(portfolio):
    first = add(portfolio, term_months=3)
    second = add(portfolio)
    third = add(portfolio)
    deposits.close_early(portfolio, third, today=JAN11)
    assert [d['id'] for d in deposits.portfolio_deposits(portfolio, today=JAN11)] == [second, first]

    deposits.settle_portfolio(portfolio, today=MAY1)
    cards = deposits.portfolio_deposits(portfolio, today=MAY1)
    assert [d['id'] for d in cards] == [second, first]
    matured = cards[1]
    assert matured['close_reason'] == 'matured'
    assert matured['next_payout'] is None and matured['forecast'] is None
    assert [n['kind'] for n in matured['notices']] == ['payout', 'matured']

    for notice in matured['notices']:
        deposits.acknowledge_notice(portfolio, notice['id'])
    assert [d['id'] for d in deposits.portfolio_deposits(portfolio, today=MAY1)] == [second]
