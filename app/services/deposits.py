import copy
from datetime import date, datetime, timedelta

from sqlalchemy import update
from sqlalchemy.orm.attributes import flag_modified

from app.formatting import fmt_number_ru
from app.models.db_session import create_session
from app.models.deposits import Deposit, DepositEvent, DepositNotice
from app.models.portfolios import Portfolio
from app.models.rates import CryptoRate, FiatRate
from . import deposit_math as dm

KINDS = ('fiat', 'crypto')
PRECISION = {'fiat': 2, 'crypto': 8}
MAX_RATE = 1000


class DepositError(Exception):
    """The message is shown to the user."""


def _events(session, deposit_id):
    return session.query(DepositEvent).filter(DepositEvent.deposit_id == deposit_id) \
        .order_by(DepositEvent.day.asc(), DepositEvent.id.asc()).all()


def _terms(dep, events):
    """(Terms, movements, rates) for deposit_math."""
    rates = [(e.day, dm.to_nominal(e.rate, e.rate_type, dep.frequency)) for e in events if e.kind in ('open', 'rate')]
    movements = [(e.day, e.amount if e.kind == 'topup' else -e.amount) for e in events if e.kind in ('topup', 'withdraw')]
    terms = dm.Terms(
        opened=dep.opened_at, amount=dep.amount,
        rate=rates[0][1] if rates else dm.to_nominal(dep.rate, dep.rate_type, dep.frequency),
        frequency=dep.frequency, capitalize=bool(dep.capitalize), base=dep.base or 'daily',
        ends=dep.ends_at, precision=PRECISION[dep.kind],
    )
    return terms, movements, rates


def _paid_out(events):
    return sum(e.amount for e in events if e.kind == 'payout')


def _amount_str(value, kind, asset):
    return f'{fmt_number_ru(value, PRECISION[kind])} {asset}'


def _holding(pf, section, asset):
    return float(pf.get_dict().get(section, {}).get(asset) or 0)


def _holding_add(pf, section, asset, delta, precision):
    data = copy.deepcopy(pf.get_dict())
    positions = data.setdefault(section, {})
    value = round(float(positions.get(asset) or 0) + delta, precision)
    if value <= 0:
        positions.pop(asset, None)
    else:
        positions[asset] = int(value) if float(value).is_integer() else value
    pf.contains = data
    flag_modified(pf, 'contains')


def _check_asset(session, kind, asset):
    if kind == 'fiat':
        if not session.query(FiatRate.id).filter(FiatRate.symbol == asset).first():
            raise DepositError('Такой валюты нет в списке поддерживаемых.')
    elif not session.query(CryptoRate.id).filter(CryptoRate.symbol == asset).first():
        raise DepositError('Такой монеты нет в списке.')


def _check_rate(rate, rate_type):
    if rate is None or not 0 <= rate <= MAX_RATE:
        raise DepositError(f'Ставка должна быть от 0 до {MAX_RATE}%.')
    if rate_type not in dm.RATE_TYPES:
        raise DepositError('Неизвестный тип ставки.')


def _check_day(dep, day, today):
    if day > today:
        raise DepositError('Дата не может быть в будущем.')
    # Earlier payouts are already in the portfolio and would no longer match
    if day < dep.last_settled_at:
        raise DepositError(f'Операцию нельзя провести раньше {dep.last_settled_at:%d.%m.%Y}: '
                           f'проценты за это время уже перенесены в портфель.')
    if dep.ends_at and day >= dep.ends_at:
        raise DepositError('Срок вклада уже закончился.')


def _active(session, deposit_id, portfolio_id):
    dep = session.get(Deposit, deposit_id)
    if not dep or dep.portfolio_id != portfolio_id:
        raise DepositError('Вклад не найден.')
    if dep.closed_at:
        raise DepositError('Вклад уже закрыт.')
    return dep


def add_deposit(portfolio_id, *, kind, asset, title, amount, rate, rate_type, frequency, capitalize,
                base='daily', opened_at=None, term_months=None, ends_at=None, take_from_holdings=False,
                today=None):
    """Adds a deposit and returns its id."""
    today = today or date.today()
    opened_at = opened_at or today
    asset = (asset or '').strip().upper()
    title = (title or '').strip() or f'Вклад в {asset}'

    if kind not in KINDS:
        raise DepositError('Неизвестный тип вклада.')
    if amount is None or amount <= 0:
        raise DepositError('Сумма должна быть больше нуля.')
    _check_rate(rate, rate_type)
    if frequency not in dm.FREQUENCIES:
        raise DepositError('Неизвестная частота выплаты процентов.')
    if base not in dm.BASES:
        raise DepositError('Неизвестный способ начисления процентов.')
    if opened_at > today:
        raise DepositError('Дата открытия не может быть в будущем.')
    if term_months:
        ends_at = dm.add_months(opened_at, int(term_months))
    if ends_at and ends_at <= opened_at:
        raise DepositError('Дата окончания должна быть позже даты открытия.')
    if frequency == 'end' and not ends_at:
        raise DepositError('Для выплаты процентов в конце срока укажите срок вклада.')
    if ends_at and ends_at <= today:
        raise DepositError('Срок этого вклада уже закончился.')

    precision = PRECISION[kind]
    amount = round(amount, precision)
    with create_session() as session:
        _check_asset(session, kind, asset)
        pf = session.get(Portfolio, portfolio_id)
        if not pf:
            raise DepositError('Портфель не найден.')
        if take_from_holdings:
            held = _holding(pf, kind, asset)
            if held < amount:
                raise DepositError(f'В портфеле только {_amount_str(held, kind, asset)}.')
            _holding_add(pf, kind, asset, -amount, precision)

        dep = Deposit(
            portfolio_id=portfolio_id, kind=kind, asset=asset, title=title[:120], amount=amount,
            rate=rate, rate_type=rate_type, frequency=frequency, capitalize=bool(capitalize), base=base,
            opened_at=opened_at, ends_at=ends_at, last_settled_at=today,
        )
        session.add(dep)
        session.flush()
        session.add(DepositEvent(deposit_id=dep.id, kind='open', day=opened_at, amount=amount,
                                 rate=rate, rate_type=rate_type, linked=bool(take_from_holdings)))
        # Opened in the past: the user already got those payouts, so they are only recorded
        if not dep.capitalize and opened_at < today:
            terms, _, rates = _terms(dep, [DepositEvent(kind='open', day=opened_at, rate=rate, rate_type=rate_type)])
            for day, value in dm.simulate(terms, today, (), rates).payouts:
                session.add(DepositEvent(deposit_id=dep.id, kind='payout', day=day, amount=value, linked=False))
        session.commit()
        return dep.id


def settle_portfolio(portfolio_id, today=None):
    """Moves due interest and matured deposits into the portfolio. Called on every portfolio view."""
    today = today or date.today()
    with create_session() as session:
        ids = [d.id for d in session.query(Deposit.id).filter(
            Deposit.portfolio_id == portfolio_id, Deposit.closed_at.is_(None))]
    return sum(1 for deposit_id in ids if _settle_one(deposit_id, today))


def _settle_one(deposit_id, today):
    with create_session() as session:
        dep = session.get(Deposit, deposit_id)
        if not dep or dep.closed_at:
            return False
        old = dep.last_settled_at
        matured = dep.ends_at is not None and today >= dep.ends_at
        upto = dep.ends_at if matured else today
        if upto <= old and not matured:
            return False

        events = _events(session, dep.id)
        terms, movements, rates = _terms(dep, events)
        res = dm.simulate(terms, upto, movements, rates)

        # Two gunicorn workers may settle the same deposit at once: SQLite lets one UPDATE through,
        # the other one no longer matches
        claimed = session.execute(
            update(Deposit)
            .where(Deposit.id == dep.id, Deposit.last_settled_at == old, Deposit.closed_at.is_(None))
            .values(last_settled_at=upto)
            .execution_options(synchronize_session=False)
        ).rowcount
        if claimed != 1:
            session.rollback()
            return False
        pf = session.get(Portfolio, dep.portfolio_id, populate_existing=True)
        precision = PRECISION[dep.kind]
        to_portfolio = 0.0
        final_interest = 0.0

        if not dep.capitalize:
            new = [(i, day, value) for i, (day, value) in enumerate(res.payouts) if day > old]
            regular = [p for p in new if not (matured and p[1] == dep.ends_at)]
            final_interest = sum(value for _, day, value in new if matured and day == dep.ends_at)
            for _, day, value in new:
                session.add(DepositEvent(deposit_id=dep.id, kind='payout', day=day, amount=value, linked=True))
            if regular:
                first = regular[0][0]
                period_from = (res.payouts[first - 1][0] if first else dep.opened_at) + timedelta(days=1)
                amount = round(sum(value for _, _, value in regular), precision)
                to_portfolio += amount
                _add_payout_notice(session, dep, amount, period_from, regular[-1][1], len(regular))

        if matured:
            back = round(res.balance + final_interest, precision)
            to_portfolio += back
            dep.closed_at, dep.close_reason, dep.returned = dep.ends_at, 'matured', back
            session.add(DepositEvent(deposit_id=dep.id, kind='close', day=dep.ends_at, amount=back, linked=True))
            session.add(DepositNotice(
                portfolio_id=dep.portfolio_id, deposit_id=dep.id, kind='matured', section=dep.kind, asset=dep.asset,
                amount=back, interest=round(res.interest, precision), principal=res.principal,
                period_from=dep.opened_at, period_to=dep.ends_at,
            ))

        if to_portfolio > 0 and pf:
            _holding_add(pf, dep.kind, dep.asset, to_portfolio, precision)
        session.commit()
        return True


def _add_payout_notice(session, dep, amount, period_from, period_to, count):
    """Payouts are added to the unread notice instead of piling up."""
    notice = session.query(DepositNotice).filter(
        DepositNotice.deposit_id == dep.id, DepositNotice.kind == 'payout',
        DepositNotice.acknowledged_at.is_(None)).first()
    if notice:
        notice.amount = round(notice.amount + amount, PRECISION[dep.kind])
        notice.period_to = period_to
        notice.payouts = (notice.payouts or 1) + count
    else:
        session.add(DepositNotice(
            portfolio_id=dep.portfolio_id, deposit_id=dep.id, kind='payout', section=dep.kind, asset=dep.asset,
            amount=amount, period_from=period_from, period_to=period_to, payouts=count,
        ))


def top_up(portfolio_id, deposit_id, amount, take_from_holdings=False, day=None, today=None):
    today = today or date.today()
    day = day or today
    _settle_one(deposit_id, today)
    with create_session() as session:
        dep = _active(session, deposit_id, portfolio_id)
        _check_day(dep, day, today)
        if amount is None or amount <= 0:
            raise DepositError('Сумма должна быть больше нуля.')
        amount = round(amount, PRECISION[dep.kind])
        if take_from_holdings:
            pf = session.get(Portfolio, dep.portfolio_id)
            held = _holding(pf, dep.kind, dep.asset)
            if held < amount:
                raise DepositError(f'В портфеле только {_amount_str(held, dep.kind, dep.asset)}.')
            _holding_add(pf, dep.kind, dep.asset, -amount, PRECISION[dep.kind])
        session.add(DepositEvent(deposit_id=dep.id, kind='topup', day=day, amount=amount, linked=bool(take_from_holdings)))
        session.commit()


def withdraw(portfolio_id, deposit_id, amount, return_to_holdings=False, day=None, today=None):
    """The whole balance may be withdrawn: the deposit stays open, like a savings account."""
    today = today or date.today()
    day = day or today
    _settle_one(deposit_id, today)
    with create_session() as session:
        dep = _active(session, deposit_id, portfolio_id)
        _check_day(dep, day, today)
        if amount is None or amount <= 0:
            raise DepositError('Сумма должна быть больше нуля.')
        amount = round(amount, PRECISION[dep.kind])
        terms, movements, rates = _terms(dep, _events(session, dep.id))
        balance = round(dm.simulate(terms, day, movements, rates).balance, PRECISION[dep.kind])
        if amount > balance:
            raise DepositError(f'На вкладе только {_amount_str(balance, dep.kind, dep.asset)}.')
        if return_to_holdings:
            pf = session.get(Portfolio, dep.portfolio_id)
            _holding_add(pf, dep.kind, dep.asset, amount, PRECISION[dep.kind])
        session.add(DepositEvent(deposit_id=dep.id, kind='withdraw', day=day, amount=amount, linked=bool(return_to_holdings)))
        session.commit()


def change_rate(portfolio_id, deposit_id, rate, rate_type='nominal', day=None, today=None):
    today = today or date.today()
    day = day or today
    _check_rate(rate, rate_type)
    _settle_one(deposit_id, today)
    with create_session() as session:
        dep = _active(session, deposit_id, portfolio_id)
        _check_day(dep, day, today)
        dep.rate, dep.rate_type = rate, rate_type
        session.add(DepositEvent(deposit_id=dep.id, kind='rate', day=day, rate=rate, rate_type=rate_type))
        session.commit()


def _close_breakdown(dep, events, day, close_rate, close_rate_type):
    terms, movements, rates = _terms(dep, events)
    paid = _paid_out(events)
    # Due but not settled yet: settlement pays them before closing
    if not dep.capitalize:
        paid += sum(value for d, value in dm.simulate(terms, day, movements, rates).payouts if d > dep.last_settled_at)
    nominal = None if close_rate is None else dm.to_nominal(close_rate, close_rate_type, dep.frequency)
    result = dm.early_close(terms, day, movements, rates, close_rate=nominal, paid_out=round(paid, PRECISION[dep.kind]))
    result['asset'] = dep.asset
    return result


def close_preview(portfolio_id, deposit_id, close_rate=None, close_rate_type='nominal', day=None, today=None):
    """{principal, interest, paid_out, holdback, returned, days, asset}; close_rate None keeps the deposit's rates."""
    today = today or date.today()
    day = day or today
    if close_rate is not None:
        _check_rate(close_rate, close_rate_type)
    with create_session() as session:
        dep = _active(session, deposit_id, portfolio_id)
        if day > today:
            raise DepositError('Дата не может быть в будущем.')
        return _close_breakdown(dep, _events(session, dep.id), day, close_rate, close_rate_type)


def close_early(portfolio_id, deposit_id, close_rate=None, close_rate_type='nominal', day=None, today=None):
    today = today or date.today()
    day = day or today
    if close_rate is not None:
        _check_rate(close_rate, close_rate_type)
    _settle_one(deposit_id, today)
    with create_session() as session:
        dep = _active(session, deposit_id, portfolio_id)
        _check_day(dep, day, today)
        result = _close_breakdown(dep, _events(session, dep.id), day, close_rate, close_rate_type)
        pf = session.get(Portfolio, dep.portfolio_id)
        if result['returned'] > 0:
            _holding_add(pf, dep.kind, dep.asset, result['returned'], PRECISION[dep.kind])
        dep.closed_at, dep.close_reason, dep.returned = day, 'early', result['returned']
        session.add(DepositEvent(deposit_id=dep.id, kind='close', day=day, amount=result['returned'], linked=True))
        session.commit()
        return result


def acknowledge_notice(portfolio_id, notice_id):
    with create_session() as session:
        notice = session.get(DepositNotice, notice_id)
        if not notice or notice.portfolio_id != portfolio_id or notice.acknowledged_at:
            return False
        notice.acknowledged_at = datetime.now()
        session.commit()
        return True


def renew_prefill(portfolio_id, deposit_id):
    """Form values for «Автопродлить»."""
    with create_session() as session:
        dep = session.get(Deposit, deposit_id)
        if not dep or dep.portfolio_id != portfolio_id or dep.close_reason != 'matured':
            return None
        months = dm.whole_months(dep.opened_at, dep.ends_at)
        return {
            'kind': dep.kind, 'asset': dep.asset, 'title': dep.title, 'amount': dep.returned,
            'rate': dep.rate, 'rate_type': dep.rate_type, 'frequency': dep.frequency,
            'capitalize': bool(dep.capitalize), 'base': dep.base, 'opened_at': dep.ends_at,
            'term_months': months,
            'ends_at': None if months else dep.ends_at + (dep.ends_at - dep.opened_at),
            'take_from_holdings': True,
        }


def _notice_dict(n):
    return {
        'id': n.id, 'deposit_id': n.deposit_id, 'kind': n.kind, 'section': n.section, 'asset': n.asset,
        'amount': n.amount, 'interest': n.interest, 'principal': n.principal,
        'period_from': n.period_from, 'period_to': n.period_to, 'payouts': n.payouts,
    }


def _deposit_dict(dep, events, today):
    terms, movements, rates = _terms(dep, events)
    now = dm.simulate(terms, min(today, dep.closed_at or today), movements, rates)
    current = rates[-1][1] if rates else terms.rate
    info = {
        'id': dep.id, 'kind': dep.kind, 'asset': dep.asset, 'title': dep.title,
        'rate': dep.rate, 'rate_type': dep.rate_type, 'nominal': current,
        'apy': dm.to_apy(current, dep.frequency) if dep.capitalize else current,
        'frequency': dep.frequency, 'capitalize': bool(dep.capitalize), 'base': dep.base,
        'opened_at': dep.opened_at, 'ends_at': dep.ends_at,
        'closed_at': dep.closed_at, 'close_reason': dep.close_reason, 'returned': dep.returned,
        'balance': now.balance, 'accrued': now.accrued, 'principal': now.principal,
        'earned': now.interest, 'paid_out': _paid_out(events),
        'next_payout': None, 'forecast': None, 'progress': None, 'days_left': None,
    }
    if dep.closed_at:
        return info

    nxt = dm.next_payout_date(terms, today)
    if nxt:
        at = dm.simulate(terms, nxt, movements, rates)
        info['next_payout'] = {'date': nxt, 'amount': at.payouts[-1][1] if at.payouts and at.payouts[-1][0] == nxt else 0.0}

    # Without further top-ups and at the current rate; a year ahead for an open-ended deposit
    target = dep.ends_at or dm.add_months(today, 12)
    end = dm.simulate(terms, target, movements, rates)
    info['forecast'] = {'date': target, 'balance': end.balance + end.accrued, 'interest': end.interest,
                        'income': end.interest - now.interest}
    if dep.ends_at:
        total = (dep.ends_at - dep.opened_at).days
        info['progress'] = min(max((today - dep.opened_at).days / total, 0.0), 1.0)
        info['days_left'] = max((dep.ends_at - today).days, 0)
    return info


def portfolio_deposits(portfolio_id, today=None):
    """Active deposits and closed ones with an unread notice, with calculated numbers and notices."""
    today = today or date.today()
    with create_session() as session:
        by_deposit = {}
        for n in session.query(DepositNotice).filter(
                DepositNotice.portfolio_id == portfolio_id, DepositNotice.acknowledged_at.is_(None)) \
                .order_by(DepositNotice.id.asc()).all():
            by_deposit.setdefault(n.deposit_id, []).append(_notice_dict(n))
        result = []
        for dep in session.query(Deposit).filter(Deposit.portfolio_id == portfolio_id).order_by(Deposit.id.desc()).all():
            if dep.closed_at and dep.id not in by_deposit:
                continue
            info = _deposit_dict(dep, _events(session, dep.id), today)
            info['notices'] = by_deposit.get(dep.id, [])
            result.append(info)
        return result


def pending_credits(portfolio_id):
    """{(section, asset): amount} for the «+16,44 € со вклада» tags."""
    credits = {}
    with create_session() as session:
        for n in session.query(DepositNotice).filter(
                DepositNotice.portfolio_id == portfolio_id, DepositNotice.acknowledged_at.is_(None)):
            key = (n.section, n.asset)
            credits[key] = round(credits.get(key, 0) + n.amount, PRECISION.get(n.section, 8))
    return credits
