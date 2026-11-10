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
