/**
 * Cart module - manages cart state and renders the cart drawer.
 */
const Cart = (() => {
  let items = []; // Array of { productId, quantity, productDetail }

  function getItems() {
    return items;
  }

  function getSize() {
    return items.reduce((sum, item) => sum + item.quantity, 0);
  }

  function getTotal() {
    return items.reduce((sum, item) => {
      return sum + (item.productDetail.price / 100) * item.quantity;
    }, 0).toFixed(2);
  }

  async function fetch() {
    try {
      const data = await Api.getCart();
      items = data.products || [];
      render();
    } catch (err) {
      console.error("Error fetching cart:", err);
    }
  }

  async function add(product) {
    try {
      const result = await Api.addToCart(product.productId, 1);
      // Update local state
      const existing = items.find(i => i.productId === result.productId || i.sk === result.productId);
      if (existing) {
        existing.quantity++;
      } else {
        items.push({
          productId: result.productId,
          sk: result.productId,
          quantity: 1,
          productDetail: product
        });
      }
      render();
      Products.render();
    } catch (err) {
      console.error("Error adding to cart:", err);
    }
  }

  async function remove(product) {
    try {
      const result = await Api.addToCart(product.productId, -1);
      const existing = items.find(i => (i.productId || i.sk) === result.productId);
      if (existing) {
        existing.quantity--;
        if (existing.quantity <= 0) {
          items = items.filter(i => (i.productId || i.sk) !== result.productId);
        }
      }
      render();
      Products.render();
    } catch (err) {
      console.error("Error removing from cart:", err);
    }
  }

  async function update(productId, quantity) {
    try {
      const result = await Api.updateCart(productId, quantity);
      const existing = items.find(i => (i.productId || i.sk) === productId);
      if (existing) {
        existing.quantity = quantity;
      }
      if (quantity <= 0) {
        items = items.filter(i => (i.productId || i.sk) !== productId);
      }
      render();
      Products.render();
    } catch (err) {
      console.error("Error updating cart:", err);
    }
  }

  async function migrate() {
    showLoading("Migrating your cart...");
    try {
      const data = await Api.migrateCart();
      items = data.products || [];
      render();
    } catch (err) {
      console.error("Error migrating cart:", err);
    }
    hideLoading();
  }

  async function checkout() {
    if (!Auth.isSignedIn()) {
      Auth.showModal();
      return;
    }
    // Show checkout modal
    document.getElementById("checkout-total").textContent = getTotal();
    const checkoutModal = bootstrap.Modal.getOrCreateInstance(document.getElementById("checkoutModal"));
    checkoutModal.show();
  }

  function initCheckoutForm() {
    document.getElementById("payment-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const form = e.target;
      if (!form.checkValidity()) {
        form.classList.add("was-validated");
        return;
      }

      bootstrap.Modal.getOrCreateInstance(document.getElementById("checkoutModal")).hide();
      showLoading("Processing payment...");

      try {
        await Api.checkoutCart();
        items = [];
        render();
        Products.render();
      } catch (err) {
        console.error("Checkout error:", err);
      }

      setTimeout(() => hideLoading(), 2000);
    });
  }

  function getQuantity(productId) {
    const item = items.find(i => (i.productId || i.sk) === productId);
    return item ? item.quantity : 0;
  }

  function render() {
    const container = document.getElementById("cart-items");
    const badge = document.getElementById("cart-badge");
    const totalEl = document.getElementById("cart-total");
    const checkoutBtn = document.getElementById("btn-checkout");
    const emptyMsg = document.getElementById("cart-empty-msg");

    const size = getSize();
    const total = getTotal();

    // Badge
    if (size > 0) {
      badge.textContent = size;
      badge.classList.remove("d-none");
    } else {
      badge.classList.add("d-none");
    }

    // Total
    totalEl.textContent = total;

    // Checkout button visibility
    if (size > 0) {
      checkoutBtn.classList.remove("d-none");
      emptyMsg.classList.add("d-none");
    } else {
      checkoutBtn.classList.add("d-none");
      emptyMsg.classList.remove("d-none");
    }

    // Cart items list
    if (items.length === 0) {
      container.innerHTML = "";
      return;
    }

    container.innerHTML = items
      .filter(item => item.quantity > 0)
      .map(item => {
        const itemTotal = ((item.productDetail.price / 100) * item.quantity).toFixed(2);
        return `
          <div class="cart-item d-flex justify-content-between align-items-center">
            <div>
              <strong>${item.productDetail.name}</strong>
              <span class="text-muted">× ${item.quantity}</span>
            </div>
            <span class="fw-bold">$${itemTotal}</span>
          </div>
        `;
      }).join("");
  }

  return {
    getItems,
    getSize,
    getTotal,
    getQuantity,
    fetch,
    add,
    remove,
    update,
    migrate,
    checkout,
    initCheckoutForm,
    render
  };
})();
