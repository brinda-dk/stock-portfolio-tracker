document.querySelectorAll("[data-password-toggle]").forEach((toggle) => {
    toggle.addEventListener("click", () => {
        const input = document.getElementById(toggle.dataset.passwordToggle);
        const isPassword = input.type === "password";
        input.type = isPassword ? "text" : "password";
        toggle.textContent = isPassword ? "Hide" : "Show";
    });
});

const quantityInput = document.getElementById("quantity");
const priceInput = document.getElementById("price_per_share");
const totalElement = document.getElementById("transaction-total");

function updateTransactionTotal() {
    if (!quantityInput || !priceInput || !totalElement) {
        return;
    }
    const total = Number(quantityInput.value) * Number(priceInput.value);
    totalElement.textContent = Number.isFinite(total) && total > 0
        ? total.toLocaleString(undefined, { style: "currency", currency: "USD" })
        : "—";
}

quantityInput?.addEventListener("input", updateTransactionTotal);
priceInput?.addEventListener("input", updateTransactionTotal);

const stockFilter = document.getElementById("stock-filter");
const stockSelect = document.getElementById("stock_id");
const stockFilterStatus = document.getElementById("stock-filter-status");

stockFilter?.addEventListener("input", () => {
    const searchTerm = stockFilter.value.trim().toLowerCase();
    let visibleCount = 0;

    Array.from(stockSelect.options).forEach((option, index) => {
        if (index === 0) {
            return;
        }
        const matches = option.dataset.search.toLowerCase().includes(searchTerm);
        option.hidden = !matches;
        visibleCount += matches ? 1 : 0;
    });

    if (stockFilterStatus) {
        stockFilterStatus.textContent = `${visibleCount} stock${visibleCount === 1 ? "" : "s"} match`;
    }
    if (stockSelect.value && stockSelect.selectedOptions[0].hidden) {
        stockSelect.value = "";
    }
});
