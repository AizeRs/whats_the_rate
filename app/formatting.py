"""Formatting helpers shared by the market and portfolio pages: numbers, prices, names, ages."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from flask import request, has_request_context
from flask_login import current_user
from app.services.symbols import MAIN_SYMBOLS
from app.utils import format_price


# Words kept as-is when prettifying Finnhub's UPPERCASE company names
_NAME_ACRONYMS = {'ETF', 'ETN', 'ADR', 'REIT', 'USA', 'US', 'U.S.', 'UK', 'S&P', 'NV', 'SA', 'AG', 'SE', 'LP',
                  'LLC', 'II', 'III', 'IV', 'NYSE', 'ESG', 'AI', 'MSCI', 'FTSE', 'SPDR', 'TR', 'PLC'}


_NAME_FIXES = {'PLC': 'Plc', 'CL': 'Class', 'CLASS': 'Class', 'ISHARES': 'iShares', 'JPMORGAN': 'JPMorgan'}


def pretty_company_name(name):
    """'AIRBNB INC-CLASS A' -> 'Airbnb Inc — Class A'. Leaves already mixed-case names untouched."""
    if not name or name != name.upper():
        return name or ''
    name = name.replace('-CL ', ' — Class ').replace('-CLASS ', ' — Class ')
    words = []
    for word in name.split():
        if word in _NAME_FIXES:
            words.append(_NAME_FIXES[word])
        elif word in _NAME_ACRONYMS or any(ch.isdigit() for ch in word) \
                or (len(word) <= 3 and not any(v in word for v in 'AEIOUY')):
            words.append(word)
        else:
            words.append('-'.join(part[:1] + part[1:].lower() for part in word.split('-')))
    return ' '.join(words)


STOCK_TYPES = {
    'Common Stock': 'Обыкновенные акции',
    'ETP': 'Биржевой фонд',
    'ADR': 'Депозитарные расписки (ADR)',
    'GDR': 'Депозитарные расписки (GDR)',
    'REIT': 'Фонд недвижимости (REIT)',
    'Preference': 'Привилегированные акции',
    'Closed-End Fund': 'Закрытый фонд',
    'Open-End Fund': 'Открытый фонд',
    'Equity WRT': 'Варрант',
    'Right': 'Права на акции',
    'Unit': 'Юниты',
    'MLP': 'Партнёрство (MLP)',
}


EXCHANGES = {'XNAS': 'NASDAQ', 'XNYS': 'NYSE', 'ARCX': 'NYSE Arca', 'XASE': 'NYSE American',
              'BATS': 'Cboe', 'OOTC': 'Внебиржевой рынок'}


def to_user_tz(moment):
    """Server-local naive datetime -> naive datetime in the visitor's timezone (browser sets the 'tz' cookie).
    Only for DISPLAY: all stored values and age arithmetic stay in server time."""
    name = request.cookies.get('tz') if has_request_context() else None
    if not moment or not name:
        return moment
    try:
        return moment.astimezone(ZoneInfo(name)).replace(tzinfo=None)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return moment


def price_age(updated_at):
    """How long ago WE saved the price: label + freshness flags for the UI."""
    if not updated_at:
        return {'label': '', 'title': '', 'fresh': False, 'very_stale': False}
    now = datetime.now()
    diff = now - updated_at
    day = timedelta(days=1)
    shown = to_user_tz(updated_at)
    shown_now = to_user_tz(now)
    today = shown_now.replace(hour=0, minute=0, second=0, microsecond=0)
    if diff < timedelta(minutes=1):
        label = 'только что'
    elif shown >= today:
        label = f'сегодня в {shown:%H:%M}'
    elif shown >= today - day:
        label = f'вчера в {shown:%H:%M}'
    elif diff < 30 * day:
        label = f'обновлено {diff.days} дн. назад'
    elif diff < 365 * day:
        label = f'обновлено {diff.days // 30} мес. назад'
    else:
        label = 'обновлено больше года назад'
    return {
        'label': label,
        'title': f'Цена сохранена на сайте {shown:%d.%m.%Y в %H:%M}. Нажмите ⟳, чтобы обновить',
        'fresh': diff < day,
        'very_stale': diff >= 30 * day,
    }


def fmt_change(pct):
    if pct is None:
        return ''
    num = f'{abs(pct):.2f}'.replace('.', ',')
    return f'▲ +{num}%' if pct >= 0 else f'▼ −{num}%'


def user_currency():
    """(code, sign, rate) of the current user's main currency."""
    code = current_user.main_currency if current_user.is_authenticated else 'USD'
    sign, rate = MAIN_SYMBOLS[code]
    return code, sign, (rate or 1.0)


def fmt_big_money(value, sign):
    """Market caps: '1 621 млрд $', '4,97 трлн $'."""
    if not value:
        return ''
    for limit, word in ((1e12, 'трлн'), (1e9, 'млрд'), (1e6, 'млн')):
        if value >= limit:
            num = value / limit
            text = f'{num:,.2f}' if num < 10 else (f'{num:,.1f}' if num < 100 else f'{num:,.0f}')
            return f"{text.replace(',', ' ').replace('.', ',')} {word} {sign}"
    return fmt_money_ru(value, sign)


def fmt_number_ru(value, max_decimals=8):
    """Formats a number Russian-style: thin-space thousands, comma decimals, no trailing zeros."""
    try:
        val = float(value)
    except (ValueError, TypeError):
        return str(value)
    text = f"{val:,.{max_decimals}f}"
    if '.' in text:
        text = text.rstrip('0').rstrip('.')
    return text.replace(',', ' ').replace('.', ',')


def fmt_money_ru(value, sign):
    """Formats a price as '85 534,00 $' (2 decimals for >= 1, more precision for small prices)."""
    try:
        val = float(value)
    except (ValueError, TypeError):
        return '—'
    if abs(val) >= 1 or val == 0:
        num = f"{val:,.2f}".replace(',', ' ').replace('.', ',')
    else:
        num = format_price(val).replace('.', ',')
    return f"{num} {sign}"


def ticker_hue(symbol):
    """Stable hue (0-359) per ticker for the coloured monogram."""
    return (sum(ord(ch) * (i + 7) for i, ch in enumerate(symbol)) * 37) % 360


# Russian name and sign for the currencies the ECB publishes
FIAT_INFO = {
    'USD': ('Доллар США', '$'), 'EUR': ('Евро', '€'), 'GBP': ('Британский фунт', '£'),
    'JPY': ('Японская иена', '¥'), 'CHF': ('Швейцарский франк', '₣'), 'AUD': ('Австралийский доллар', 'A$'),
    'BGN': ('Болгарский лев', 'лв'), 'BRL': ('Бразильский реал', 'R$'), 'CAD': ('Канадский доллар', 'C$'),
    'CNY': ('Китайский юань', '¥'), 'CZK': ('Чешская крона', 'Kč'), 'DKK': ('Датская крона', 'kr'),
    'HKD': ('Гонконгский доллар', 'HK$'), 'HUF': ('Венгерский форинт', 'Ft'), 'IDR': ('Индонезийская рупия', 'Rp'),
    'ILS': ('Израильский шекель', '₪'), 'INR': ('Индийская рупия', '₹'), 'ISK': ('Исландская крона', 'kr'),
    'KRW': ('Южнокорейская вона', '₩'), 'MXN': ('Мексиканское песо', '$'), 'MYR': ('Малайзийский ринггит', 'RM'),
    'NOK': ('Норвежская крона', 'kr'), 'NZD': ('Новозеландский доллар', 'NZ$'), 'PHP': ('Филиппинское песо', '₱'),
    'PLN': ('Польский злотый', 'zł'), 'RON': ('Румынский лей', 'lei'), 'RUB': ('Российский рубль', '₽'),
    'SEK': ('Шведская крона', 'kr'), 'SGD': ('Сингапурский доллар', 'S$'), 'THB': ('Тайский бат', '฿'),
    'TRY': ('Турецкая лира', '₺'), 'ZAR': ('Южноафриканский рэнд', 'R'),
}


MONTHS_GENITIVE = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа',
                    'сентября', 'октября', 'ноября', 'декабря']


def fiat_unit(price):
    """Small currencies are quoted per 100 / 1000 / 10 000 units, like banks do."""
    if price >= 0.01:
        return 1
    unit = 100
    while price * unit < 0.1:
        unit *= 10
    return unit


def fmt_fiat_price(value, sign):
    num = f"{value:,.{2 if value >= 1 else 4}f}".replace(',', '\u202f').replace('.', ',')
    return f"{num}\u00a0{sign}"
