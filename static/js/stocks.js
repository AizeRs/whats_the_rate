// Stocks page: refresh of one stock's price (each row has its own button). Shared code: market.js
(function () {
    const PRICE_ERRORS = {
        limit: 'Finnhub временно ограничил запросы цен. Подождите минуту и попробуйте снова.',
        no_data: 'Finnhub не вернул цену для этого тикера. Попробуйте позже.',
        error: 'Не удалось получить цену. Попробуйте ещё раз.'
    };

    // quiet = true: automatic refresh, stays silent unless Finnhub refuses because of the rate limit
    async function refreshPrice(btn, quiet) {
        if (btn.disabled) return;
        const row = btn.closest('.stock-row');
        const icon = btn.querySelector('.material-symbols-outlined');
        btn.disabled = true;
        icon.classList.add('animate-spin');
        try {
            const data = await App.post({ reload_rate: btn.dataset.ticker });
            if (data.price_html !== undefined) {
                row.querySelector('.price-cell').innerHTML = data.price_html;
                const valueCell = row.querySelector('.value-cell');
                if (valueCell) valueCell.innerHTML = data.value_html;
                const container = row.querySelector('.portfolio-action-container');
                if (container) container.dataset.price = data.price_num;
            }
            if (!quiet || data.status === 'limit') {
                App.toast(data.success ? null : (PRICE_ERRORS[data.status] || PRICE_ERRORS.error));
            }
        } catch (err) {
            console.error('Error refreshing price:', err);
            if (!quiet) App.toast(PRICE_ERRORS.error);
        } finally {
            icon.classList.remove('animate-spin');
            btn.disabled = false;
        }
    }

    document.addEventListener('click', e => {
        const btn = e.target.closest('.refresh-btn');
        if (btn) refreshPrice(btn, false);
    });

    // /stocks: refresh the user's own stocks whose price is older than 15 minutes, one after another
    (async function () {
        for (const btn of document.querySelectorAll('.refresh-btn[data-auto-refresh]')) {
            await refreshPrice(btn, true);
        }
    })();
})();
