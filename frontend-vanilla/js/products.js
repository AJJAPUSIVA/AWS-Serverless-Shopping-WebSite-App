/**
 * Products module - fetches and renders the product grid.
 */
const Products = (() => {
  let products = [];

  async function fetch() {
    try {
      const data = await Api.getProducts();
      products = data.products || [];
      render();
    } catch (err) {
      console.error("Error fetching products:", err);
      document.getElementById("products-grid").innerHTML = `
        <div class="col-12 text-center text-danger">
          <p>Failed to load products. Check your API configuration in <code>js/config.js</code>.</p>
        </div>
      `;
    }
  }

  function render() {
    const grid = document.getElementById("products-grid");

    if (!products.length) {
      grid.innerHTML = `<div class="col-12 text-center text-muted"><p>Loading products...</p></div>`;
      return;
    }

    grid.innerHTML = products.map(product => {
      const price = (product.price / 100).toFixed(2);
      const qty = Cart.getQuantity(product.productId);

      return `
        <div class="col-12 col-sm-6 col-lg-4">
          <div class="product-card card p-3">
            <div class="card-body">
              <div class="d-flex justify-content-between align-items-start mb-2">
                <h6 class="card-title mb-0">${product.name}</h6>
                <span class="category-badge">${product.category}</span>
              </div>
              <p class="card-text text-muted small mb-2">"${product.description}"</p>
              <p class="price mb-0">$${price}</p>
            </div>
            <div class="card-footer bg-transparent border-0 text-center pt-0">
              <div class="quantity-controls mx-auto">
                <button onclick="Cart.remove(getProduct('${product.productId}'))" ${qty < 1 ? "disabled" : ""} aria-label="Remove one">
                  <i class="bi bi-dash"></i>
                </button>
                <span class="qty-value">${qty}</span>
                <button onclick="Cart.add(getProduct('${product.productId}'))" aria-label="Add one">
                  <i class="bi bi-plus"></i>
                </button>
              </div>
            </div>
          </div>
        </div>
      `;
    }).join("");
  }

  function getAll() {
    return products;
  }

  function getById(productId) {
    return products.find(p => p.productId === productId) || null;
  }

  return { fetch, render, getAll, getById };
})();

// Global helper for inline onclick handlers
function getProduct(productId) {
  return Products.getById(productId);
}
