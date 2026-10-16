// Portfolio page (owner only): quantities, removal with undo, price reload.
// The tables are re-rendered by the server after every change, so all buttons are handled by delegation.
(function () {
    const root = document.querySelector('[data-portfolio]');
    if (!root) return;
    const { showEl, parseQty, toast } = App;
    let undoState = null;
    let undoTimer = null;

    // Every change returns the new tables
    async function post(body) {
        const data = await App.post(body);
        if (data.html !== undefined) document.getElementById('portfolioBody').innerHTML = data.html;
        return data;
    }

    function copyLink(btn) {
        navigator.clipboard.writeText(btn.dataset.url).then(() => {
            const text = btn.querySelector('[data-copy-text]');
            text.textContent = 'Ссылка скопирована';
            setTimeout(() => { text.textContent = 'Скопировать ссылку'; }, 1800);
        });
    }

    /* ---------- Prices ---------- */
    // auto = true: some prices are stale, reload them right after the page opens (silently)
    async function reloadPrices(auto) {
        const btn = document.getElementById('reloadBtn');
        if (!btn || btn.disabled) return;
        const icon = btn.querySelector('[data-reload-icon]');
        const text = btn.querySelector('[data-reload-text]');
        btn.disabled = true;
        icon.classList.add('animate-spin');
        text.textContent = 'Обновление…';
        try {
            const data = await post({ reload: auto ? 'auto' : 'all' });
            toast(data.success || auto ? null : data.message);
        } catch (err) {
            console.error('Error reloading prices:', err);
            if (!auto) toast('Не удалось обновить цены. Попробуйте ещё раз.');
        } finally {
            icon.classList.remove('animate-spin');
            text.textContent = 'Обновить цены';
            btn.disabled = false;
        }
    }

    /* ---------- Quantities ---------- */
    function setEditing(row, editing) {
        row.classList.toggle('editing', editing);
        showEl(row.querySelector('.qty-edit'), editing);
        row.querySelector('.qty-view').classList.toggle('hidden', editing);
        showEl(row.querySelector('.edit-actions'), editing);
        showEl(row.querySelector('.view-actions'), !editing);
    }

    function editQty(row) {
        document.querySelectorAll('.asset-row').forEach(r => setEditing(r, false));
        const input = row.querySelector('.qty-input');
        input.value = String(row.dataset.qty).replace('.', ',');
        setEditing(row, true);
        input.focus();
        input.select();
    }

    async function saveQty(row) {
        const qty = parseQty(row.querySelector('.qty-input').value);
        if (qty === null || qty < 0) { row.querySelector('.qty-input').focus(); return; }
        row.querySelector('.save-btn').disabled = true;
        try {
            const data = await post({ kind: row.dataset.kind, code: row.dataset.code, quantity: qty });
            toast(data.success ? null : data.message);
        } catch (err) {
            console.error('Error saving quantity:', err);
            toast('Не удалось сохранить. Попробуйте ещё раз.');
        }
    }

    async function removeAsset(row) {
        const state = { kind: row.dataset.kind, code: row.dataset.code, quantity: row.dataset.qty };
        try {
            const data = await post({ kind: state.kind, code: state.code, quantity: 0 });
            if (!data.success) { toast(data.message); return; }
            undoState = state;
            document.getElementById('undoText').textContent = state.code + ' убран из портфеля';
            showEl(document.getElementById('undoBar'), true);
            clearTimeout(undoTimer);
            undoTimer = setTimeout(() => { showEl(document.getElementById('undoBar'), false); undoState = null; }, 8000);
        } catch (err) {
            console.error('Error removing asset:', err);
            toast('Не удалось убрать актив. Попробуйте ещё раз.');
        }
    }

    async function undoRemove() {
        if (!undoState) return;
        const state = undoState;
        undoState = null;
        showEl(document.getElementById('undoBar'), false);
        const data = await post(state);
        toast(data.success ? null : data.message);
    }

    document.addEventListener('click', e => {
        const btn = e.target.closest('[data-pf-action]');
        if (!btn) return;
        const row = btn.closest('.asset-row');
        switch (btn.dataset.pfAction) {
            case 'edit': editQty(row); break;
            case 'cancel': setEditing(row, false); break;
            case 'save': saveQty(row); break;
            case 'remove': removeAsset(row); break;
            case 'undo': undoRemove(); break;
            case 'reload': reloadPrices(false); break;
            case 'copy-link': copyLink(btn); break;
        }
    });
    document.addEventListener('keydown', e => {
        if (!e.target.classList.contains('qty-input')) return;
        const row = e.target.closest('.asset-row');
        if (e.key === 'Enter') { e.preventDefault(); saveQty(row); }
        else if (e.key === 'Escape') { e.preventDefault(); setEditing(row, false); }
    });

    if ('autoReload' in root.dataset) reloadPrices(true);
})();
