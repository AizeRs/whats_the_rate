// Home page: tabs of the quotes table and background reload of old quotes.
// Settings on the page root: data-auto-crypto / data-auto-fiat (+ their page URLs)
(function () {
    const root = document.querySelector('[data-home]');
    if (!root) return;

    // Tabs of the quotes table
    const tabs = document.querySelectorAll('.home-tab');
    tabs.forEach(function (tab) {
        tab.addEventListener('click', function () {
            const key = tab.dataset.tab;
            tabs.forEach(function (t) {
                const on = t === tab;
                t.setAttribute('aria-selected', on);
                t.classList.toggle('text-on-surface', on);
                t.classList.toggle('shadow-[inset_0_-2px_0_#3b82f6]', on);
                t.classList.toggle('text-outline', !on);
            });
            document.querySelectorAll('.market-panel').forEach(function (p) { p.classList.toggle('is-active', p.dataset.panel === key); });
            document.querySelectorAll('[data-note]').forEach(function (n) { n.classList.toggle('lg:!hidden', n.dataset.note !== key); });
        });
    });

    (async function () {
        // Old crypto / fiat quotes: reload them on the server, then show the page again (the server limits retries)
        let reloaded = false;
        try {
            if ('autoCrypto' in root.dataset) reloaded = (await App.post({ reload_crypto: 1 }, root.dataset.cryptoUrl)).success || reloaded;
            if ('autoFiat' in root.dataset) reloaded = (await App.post({ reload_fiat: 1 }, root.dataset.fiatUrl)).success || reloaded;
        } catch (err) { console.error('Error reloading quotes:', err); }
        if (reloaded) { window.location.reload(); return; }

        // Outdated stock prices: one by one, each row is replaced in place
        for (const row of document.querySelectorAll('[data-refresh]')) {
            try {
                const data = await App.post({ refresh_stock: row.dataset.refresh });
                if (data.html) row.outerHTML = data.html;
                if (data.status === 'limit') break;  // Finnhub's rate limit: the rest waits for the next visit
            } catch (err) { console.error('Error refreshing price:', err); }
        }
    })();
})();
