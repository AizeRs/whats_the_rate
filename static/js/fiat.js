// Fiat page: the list is filtered right away as you type. Shared code: market.js
(function () {
    const input = document.querySelector('[data-search-input]');
    if (!input) return;
    input.addEventListener('input', () => {
        const query = input.value.trim();
        const q = query.toLowerCase();
        let shown = 0;
        document.querySelectorAll('.fiat-row').forEach(row => {
            const match = !q || row.dataset.search.includes(q);
            row.classList.toggle('hidden', !match);
            if (match) shown++;
        });
        document.getElementById('fiatCount').textContent = shown;
        document.getElementById('fiatListTitle').textContent = q ? 'Результаты поиска «' + query + '»' : 'Все валюты';
        App.showEl(document.getElementById('fiatEmpty'), shown === 0);
    });
})();
