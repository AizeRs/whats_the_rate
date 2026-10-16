// Profile page: the two dropdowns (portfolio visibility, display currency) and copying the API key.
// Password eye buttons are handled in common.js.
(function () {
    const dropdowns = ['portfolio-dropdown', 'currency-dropdown'].map(id => document.getElementById(id)).filter(Boolean);

    document.addEventListener('click', e => {
        const toggle = e.target.closest('[data-dropdown-toggle]');
        // Open the clicked one, close the others (also on any click outside)
        dropdowns.forEach(d => {
            if (toggle && toggle.dataset.dropdownToggle === d.id) d.classList.toggle('hidden');
            else if (!e.target.closest('#' + d.id)) d.classList.add('hidden');
        });

        const copyBtn = e.target.closest('[data-copy-api-key]');
        if (copyBtn) {
            navigator.clipboard.writeText(document.getElementById('api-key-value').textContent.trim());
            const icon = copyBtn.querySelector('.material-symbols-outlined');
            icon.textContent = 'done';
            icon.classList.add('text-tertiary');
            setTimeout(() => {
                icon.textContent = 'content_copy';
                icon.classList.remove('text-tertiary');
            }, 2000);
        }
    });
})();
