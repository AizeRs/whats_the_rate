// Shared code of the market pages (stocks, crypto, fiat). The page root carries the settings:
//   data-market="stocks|crypto|fiat"   data-currency-sign="$"   data-auto-reload="reload_crypto" (data is old)
(function () {
    const root = document.querySelector('[data-market]');
    if (!root) return;
    const { post, showEl, parseQty, fmtMoney, fmtQty } = App;
    const kind = root.dataset.market;
    const sign = root.dataset.currencySign;
    const MAX_STOCKS = 5;

    /* ---------- Old quotes / ticker list: reloaded in the background ---------- */
    // data-auto-reload="<request key>" is set by the server when the data is old (app/auto_reload.py).
    // The server checks again and limits retries; with fresh data the page is shown again.
    if (root.dataset.autoReload) {
        post({ [root.dataset.autoReload]: 1 })
            .then(data => { if (data.success) window.location.reload(); })
            .catch(err => console.error('Error reloading quotes:', err));
    }

    /* ---------- Search box ---------- */
    const searchForm = document.querySelector('[data-search-url]');
    const searchInput = document.querySelector('[data-search-input]');
    const clearBtn = document.querySelector('[data-search-clear]');

    // Stocks and crypto: the query goes into the URL (/stocks/<query>)
    if (searchForm) {
        searchForm.addEventListener('submit', e => {
            e.preventDefault();
            const v = searchInput.value.trim();
            window.location.href = searchForm.dataset.searchUrl + (v ? '/' + encodeURIComponent(v) : '');
        });
    }
    if (searchInput) {
        // Phones: a shorter placeholder that fits the narrow field
        if (searchInput.dataset.shortPlaceholder && window.matchMedia('(max-width: 639px)').matches) {
            searchInput.placeholder = searchInput.dataset.shortPlaceholder;
        }
        // The clear (×) button is shown only when there is text
        searchInput.addEventListener('input', () => clearBtn.classList.toggle('hidden', !searchInput.value));
        clearBtn.addEventListener('click', () => {
            searchInput.value = '';
            searchInput.dispatchEvent(new Event('input'));
            searchInput.focus();
        });
    }

    /* ---------- Mobile filter by the first symbol (templates/_letter_filter.html) ---------- */
    const sheet = document.getElementById('letterSheet');
    if (sheet) {
        const toggleSheet = open => {
            sheet.classList.toggle('hidden', !open);
            document.body.classList.toggle('overflow-hidden', open);
        };
        document.addEventListener('click', e => {
            const btn = e.target.closest('[data-letter-sheet]');
            if (btn) toggleSheet(btn.dataset.letterSheet === 'open');
        });
        document.addEventListener('keydown', e => { if (e.key === 'Escape') toggleSheet(false); });
        // Scroll the selected symbol into the visible part of the strip
        const strip = document.getElementById('letterStrip');
        const current = strip && strip.querySelector('[aria-current]');
        if (current) strip.scrollLeft = current.offsetLeft - (strip.clientWidth - current.offsetWidth) / 2;
    }

    /* ---------- Portfolio: the quantity editor in each row (templates/_portfolio_action.html) ---------- */
    const KEYS = { stocks: ['add_stock', 'set_stock'], crypto: ['add_crypto', 'set_crypto'], fiat: ['add_fiat', 'set_fiat'] }[kind];

    function updateEstimate(container) {
        const qty = parseQty(container.querySelector('.quantity-input').value);
        const price = parseFloat(container.dataset.price);
        container.querySelector('.estimate').textContent =
            !price ? 'цена не загружена' : (qty && qty > 0 ? '≈ ' + fmtMoney(qty * price, sign) : '≈ —');
    }

    function restoreIdle(container) {
        const held = parseFloat(container.dataset.held) || 0;
        container.classList.remove('editing');
        showEl(container.querySelector('.input-mode'), false);
        showEl(container.querySelector('.error-badge'), false);
        showEl(container.querySelector('.default-mode'), held <= 0);
        showEl(container.querySelector('.held-mode'), held > 0);
    }

    // mode: 'add' adds to what is held, 'set' replaces it
    function openEditor(container, mode) {
        document.querySelectorAll('.portfolio-action-container.editing').forEach(c => { if (c !== container) restoreIdle(c); });
        container.dataset.mode = mode;
        container.classList.add('editing');
        showEl(container.querySelector('.default-mode'), false);
        showEl(container.querySelector('.held-mode'), false);
        showEl(container.querySelector('.input-mode'), true);
        const input = container.querySelector('.quantity-input');
        const held = parseFloat(container.dataset.held) || 0;
        input.value = (mode === 'set' && held > 0) ? String(held).replace('.', ',') : '';
        updateEstimate(container);
        input.focus();
        input.select();
    }

    // Stocks: at most 5 in a portfolio, the add buttons are disabled when it is full
    function setStocksFull(full) {
        showEl(document.getElementById('stocksFullNote'), full);
        document.querySelectorAll('.portfolio-action-container').forEach(c => {
            const add = c.querySelector('.default-mode');
            add.disabled = full;
            add.title = full ? 'В портфеле может быть не больше 5 акций' : 'Добавить ' + c.dataset.ticker + ' в портфель';
        });
    }

    async function save(container) {
        const mode = container.dataset.mode || 'add';
        const input = container.querySelector('.quantity-input');
        const confirmBtn = container.querySelector('.confirm-btn');
        const cancelBtn = container.querySelector('.cancel-btn');

        let qty = parseQty(input.value);
        if (mode === 'add') {
            if (qty === null || qty <= 0) qty = 1;
        } else if (qty === null || qty < 0) {
            input.focus();
            return;
        }

        confirmBtn.disabled = cancelBtn.disabled = true;
        confirmBtn.innerHTML = '<span class="material-symbols-outlined text-[16px] animate-spin leading-none">progress_activity</span>';
        const resetBtn = () => {
            confirmBtn.disabled = cancelBtn.disabled = false;
            confirmBtn.innerHTML = '<span class="material-symbols-outlined text-[18px] leading-none">check</span>';
        };

        try {
            const data = await post({ [KEYS[mode === 'set' ? 1 : 0]]: container.dataset.ticker, quantity: qty });
            resetBtn();
            if (data.success) {
                const total = parseFloat(data.quantity) || 0;
                const label = data.quantity_str || fmtQty(total);
                container.dataset.held = total;
                container.querySelector('.held-qty').textContent = label;
                // Phones: the held quantity is also shown under the asset name
                const row = container.parentElement;
                const heldSub = row.querySelector('.held-sub');
                if (heldSub) {
                    heldSub.querySelector('.held-qty-sub').textContent = label;
                    heldSub.classList.toggle('hidden', total <= 0);
                    const coinId = row.querySelector('.coin-id');
                    if (coinId) coinId.classList.toggle('max-sm:hidden', total > 0);
                }
                restoreIdle(container);
            } else if (data.reason === 'limit') {
                restoreIdle(container);
            } else {
                showEl(container.querySelector('.input-mode'), false);
                showEl(container.querySelector('.error-badge'), true);
                setTimeout(() => restoreIdle(container), 2500);
            }
            if (data.stocks_count !== undefined) setStocksFull(data.stocks_count >= MAX_STOCKS);
        } catch (err) {
            console.error('Error updating portfolio:', err);
            resetBtn();
        }
    }

    document.addEventListener('click', e => {
        const btn = e.target.closest('[data-qty-action]');
        if (!btn) return;
        const container = btn.closest('.portfolio-action-container');
        const action = btn.dataset.qtyAction;
        if (action === 'save') save(container);
        else if (action === 'cancel') restoreIdle(container);
        else openEditor(container, action);  // 'add' or 'set'
    });
    document.addEventListener('input', e => {
        if (e.target.classList.contains('quantity-input')) updateEstimate(e.target.closest('.portfolio-action-container'));
    });
    document.addEventListener('keydown', e => {
        if (!e.target.classList.contains('quantity-input')) return;
        const container = e.target.closest('.portfolio-action-container');
        if (e.key === 'Enter') { e.preventDefault(); save(container); }
        else if (e.key === 'Escape') { e.preventDefault(); restoreIdle(container); }
    });
})();
