// Sign-in / sign-up page: the two forms slide sideways, the URL follows (/login <-> /register).
// Password eye buttons are handled in common.js.
(function () {
    const root = document.getElementById('auth');
    const viewport = root.querySelector('.auth-viewport');
    const titles = { login: 'Вход', register: 'Регистрация' };
    const urls = { login: root.dataset.loginUrl, register: root.dataset.registerUrl };
    const desktop = window.matchMedia('(min-width: 1024px)');

    // The two forms differ in height: the viewport follows the visible one
    function fitHeight() {
        viewport.style.height = root.querySelector('[data-pane="' + root.dataset.mode + '"]').offsetHeight + 'px';
    }

    function markPanes() {
        root.querySelectorAll('[data-pane]').forEach(function (pane) {
            const hidden = pane.dataset.pane !== root.dataset.mode;
            pane.inert = hidden;
            pane.setAttribute('aria-hidden', hidden);
        });
        root.querySelectorAll('.auth-tab').forEach(function (tab) {
            if (tab.dataset.switch === root.dataset.mode) tab.setAttribute('aria-current', 'page');
            else tab.removeAttribute('aria-current');
        });
    }

    function setMode(mode, push) {
        if (mode === root.dataset.mode) return;
        root.dataset.mode = mode;
        markPanes();
        document.title = titles[mode] + " · What's the rate";
        fitHeight();
        if (push) history.pushState({ authMode: mode }, '', urls[mode]);
        const first = root.querySelector('[data-pane="' + mode + '"] input:not([type=hidden])');
        if (first && desktop.matches) setTimeout(function () { first.focus({ preventScroll: true }); }, 450);
    }

    root.querySelectorAll('[data-switch]').forEach(function (link) {
        link.addEventListener('click', function (e) {
            e.preventDefault();
            setMode(link.dataset.switch, true);
        });
    });
    window.addEventListener('popstate', function () {
        setMode(location.pathname.replace(/\/$/, '').endsWith('register') ? 'register' : 'login', false);
    });
    window.addEventListener('resize', fitHeight);
    // Web fonts change the height of the panes once they arrive
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(fitHeight);

    // Initial state: hide the inactive form from keyboard and screen readers (no animation)
    markPanes();
    fitHeight();
    history.replaceState({ authMode: root.dataset.mode }, '', location.href);
})();
