import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta

FREQUENCIES = ('daily', 'monthly', 'quarterly', 'yearly', 'end')
BASES = ('daily', 'min')
RATE_TYPES = ('nominal', 'apy')
_MONTH_STEP = {'monthly': 1, 'quarterly': 3, 'yearly': 12}
_PERIODS_PER_YEAR = {'daily': 365, 'monthly': 12, 'quarterly': 4, 'yearly': 1}


def add_months(d, months):
    """31 Jan + 1 month -> 28/29 Feb."""
    m = d.month - 1 + months
    year, month = d.year + m // 12, m % 12 + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def whole_months(start, end):
    """Number of months between the dates, or None if it isn't whole."""
    months = (end.year - start.year) * 12 + end.month - start.month
    return months if months > 0 and add_months(start, months) == end else None


def days_in_year(year):
    return 366 if calendar.isleap(year) else 365


def to_nominal(rate_pct, rate_type, frequency):
    """Nominal annual rate as a fraction."""
    rate = rate_pct / 100
    n = _PERIODS_PER_YEAR.get(frequency)
    if rate_type == 'apy' and n:
        return n * ((1 + rate) ** (1 / n) - 1)
    return rate


def to_apy(nominal, frequency):
    n = _PERIODS_PER_YEAR.get(frequency)
    return (1 + nominal / n) ** n - 1 if n else nominal


@dataclass
class Terms:
    opened: date
    amount: float
    rate: float  # Nominal, fraction
    frequency: str
    capitalize: bool
    base: str = 'daily'
    ends: date = None
    precision: int = 2


@dataclass
class Result:
    balance: float  # Includes capitalized interest
    accrued: float  # Interest of the current period, not paid yet
    payouts: list = field(default_factory=list)  # [(date, amount)]
    principal: float = 0.0  # Amount + top-ups - withdrawals
    matured: bool = False

    @property
    def interest(self):
        return sum(a for _, a in self.payouts) + self.accrued


def payout_dates(terms, until):
    """Period ends up to `until`: monthly anniversaries of the opening date, the last one on the end date."""
    last = min(until, terms.ends) if terms.ends else until
    if terms.frequency == 'end':
        if terms.ends and terms.ends <= until:
            yield terms.ends
        return
    if terms.frequency == 'daily':
        d = terms.opened + timedelta(days=1)
        while d <= last:
            yield d
            d += timedelta(days=1)
        return
    step = _MONTH_STEP[terms.frequency]
    k = 1
    while True:
        d = add_months(terms.opened, k * step)
        if terms.ends and d >= terms.ends:
            if terms.ends <= until:
                yield terms.ends
            return
        if d > until:
            return
        yield d
        k += 1


def next_payout_date(terms, after):
    if terms.frequency == 'end':
        return terms.ends if terms.ends and terms.ends > after else None
    if terms.frequency == 'daily':
        d = max(after, terms.opened) + timedelta(days=1)
        return d if not terms.ends or d <= terms.ends else None
    step = _MONTH_STEP[terms.frequency]
    k = 1
    while True:
        d = add_months(terms.opened, k * step)
        if terms.ends and d >= terms.ends:
            return terms.ends if terms.ends > after else None
        if d > after:
            return d
        k += 1


def simulate(terms, until, movements=(), rates=()):
    """Runs the deposit day by day up to `until`.

    movements: [(date, delta)], negative for withdrawals. rates: [(date, nominal)], from that day on.
    """
    if terms.frequency == 'end' and not terms.ends:
        raise ValueError('A deposit paid at the end needs an end date')
    last = min(until, terms.ends) if terms.ends else until

    moves = {}
    balance = terms.amount
    for d, delta in movements:
        if d <= terms.opened:
            balance += delta
        else:
            moves[d] = moves.get(d, 0) + delta
    principal = terms.amount + sum(delta for _, delta in movements)
    rate_changes = sorted(rates)
    rate, ri = terms.rate, 0
    while ri < len(rate_changes) and rate_changes[ri][0] <= terms.opened:
        rate = rate_changes[ri][1]
        ri += 1

    pay_days = set(payout_dates(terms, last))
    payouts = []
    accrued = 0.0
    factor = 0.0  # 'min' base: sum of daily rates in the period
    period_min = balance

    d = terms.opened + timedelta(days=1)
    while d <= last:
        while ri < len(rate_changes) and rate_changes[ri][0] <= d:
            rate = rate_changes[ri][1]
            ri += 1
        daily_rate = rate / days_in_year(d.year)
        if terms.base == 'min':
            factor += daily_rate
        else:
            accrued += balance * daily_rate

        # Civil Code art. 839: money earns from the day after it comes in and up to the day it is taken out,
        # so movements apply at the end of their day
        delta = moves.get(d)
        if delta:
            balance += delta
            if delta < 0:
                period_min = min(period_min, balance)

        if d in pay_days:
            interest = period_min * factor if terms.base == 'min' else accrued
            interest = round(interest, terms.precision)
            payouts.append((d, interest))
            if terms.capitalize:
                balance += interest
            accrued, factor, period_min = 0.0, 0.0, balance
        d += timedelta(days=1)

    if terms.base == 'min':
        accrued = period_min * factor
    return Result(balance=balance, accrued=accrued, payouts=payouts, principal=principal,
                  matured=bool(terms.ends) and until >= terms.ends)


def early_close(terms, on, movements=(), rates=(), close_rate=None, paid_out=0.0):
    """close_rate: the bank recalculates the whole term with it (None keeps the actual rates).
    Interest paid out above the recalculated one is held back from the principal."""
    if close_rate is not None:
        terms = Terms(**{**terms.__dict__, 'rate': close_rate})
        rates = ()
    res = simulate(terms, on, movements, rates)
    interest = round(res.interest, terms.precision)
    returned = round(res.principal + interest - paid_out, terms.precision)
    return {
        'principal': res.principal,
        'interest': interest,
        'paid_out': paid_out,
        'holdback': round(max(paid_out - interest, 0.0), terms.precision),
        'returned': max(returned, 0.0),
        'days': (on - terms.opened).days,
    }
