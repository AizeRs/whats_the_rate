// Helpers shared by every page (loaded at the end of <body>, before the page's own script).
const App = (function () {
    // POST JSON to the current page (or `url`) the way the server's AJAX handlers expect
    function post(body, url) {
        return fetch(url || window.location.pathname, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
            body: JSON.stringify(body)
        }).then(r => r.json());
    }

    // Show / hide an element that is laid out with flex when visible
    function showEl(el, show) {
        if (!el) return;
        el.classList.toggle('hidden', !show);
        el.classList.toggle('flex', show);
    }

    // "1 234,5" -> 1234.5; null when it isn't a number
    function parseQty(raw) {
        const v = parseFloat(String(raw).replace(/\s/g, '').replace(',', '.'));
        return isNaN(v) ? null : v;
    }

    // Money in Russian format; sums under 1 keep up to 6 decimals (cheap coins)
    function fmtMoney(v, sign) {
        const digits = Math.abs(v) >= 1 || v === 0 ? 2 : 6;
        return new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: digits }).format(v) + ' ' + sign;
    }

    function fmtQty(v) {
        return new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 8 }).format(v);
    }

    // The red notice of a page (<div data-toast> with <span data-toast-text>); null hides it
    function toast(text) {
        const box = document.querySelector('[data-toast]');
        if (!box) return;
        if (text) box.querySelector('[data-toast-text]').textContent = text;
        showEl(box, !!text);
    }

    return { post, showEl, parseQty, fmtMoney, fmtQty, toast };
})();

document.addEventListener('click', function (e) {
    // Password fields: the eye button shows / hides the password.
    // data-toggle-password="<input id>", or empty for the input next to the button
    const eye = e.target.closest('[data-toggle-password]');
    if (eye) {
        const id = eye.dataset.togglePassword;
        const input = id ? document.getElementById(id) : eye.parentElement.querySelector('input');
        const show = input.type === 'password';
        input.type = show ? 'text' : 'password';
        eye.querySelector('.material-symbols-outlined').textContent = show ? 'visibility_off' : 'visibility';
        eye.setAttribute('aria-label', show ? 'Скрыть пароль' : 'Показать пароль');
    }
    if (e.target.closest('[data-toast-close]')) App.toast(null);
});
