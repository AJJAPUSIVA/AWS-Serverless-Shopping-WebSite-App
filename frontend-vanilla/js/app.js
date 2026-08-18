/**
 * App initialization - entry point.
 */

// Utility: show/hide loading overlay
function showLoading(message = "") {
  const overlay = document.getElementById("loading-overlay");
  const text = document.getElementById("loading-text");
  text.textContent = message;
  overlay.classList.remove("d-none");
}

function hideLoading() {
  document.getElementById("loading-overlay").classList.add("d-none");
}

// Initialize all modules on DOM ready
document.addEventListener("DOMContentLoaded", () => {
  Auth.init();
  Cart.initCheckoutForm();
  Assistant.init();

  // Load data
  Products.fetch();
  Cart.fetch();
});
