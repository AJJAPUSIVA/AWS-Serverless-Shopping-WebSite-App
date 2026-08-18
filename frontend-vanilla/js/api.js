/**
 * API module - handles all HTTP communication with the backend.
 * Uses native fetch() with proper auth headers.
 */
const Api = (() => {

  async function getHeaders(includeAuth = false) {
    const headers = { "Content-Type": "application/json" };
    if (includeAuth) {
      const token = await Auth.getIdToken();
      if (token) {
        headers["Authorization"] = token;
      }
    }
    return headers;
  }

  async function getProducts() {
    const headers = await getHeaders();
    const res = await fetch(CONFIG.PRODUCTS_API_URL + "/product", {
      method: "GET",
      headers
    });
    if (!res.ok) throw new Error("Failed to fetch products");
    return res.json();
  }

  async function getCart() {
    const headers = await getHeaders(true);
    const res = await fetch(CONFIG.CART_API_URL + "/cart", {
      method: "GET",
      headers,
      credentials: "include"
    });
    if (!res.ok) throw new Error("Failed to fetch cart");
    return res.json();
  }

  async function addToCart(productId, quantity = 1) {
    const headers = await getHeaders(true);
    const res = await fetch(CONFIG.CART_API_URL + "/cart", {
      method: "POST",
      headers,
      credentials: "include",
      body: JSON.stringify({ productId, quantity })
    });
    if (!res.ok) throw new Error("Failed to add to cart");
    return res.json();
  }

  async function updateCart(productId, quantity) {
    const headers = await getHeaders(true);
    const res = await fetch(CONFIG.CART_API_URL + "/cart/" + productId, {
      method: "PUT",
      headers,
      credentials: "include",
      body: JSON.stringify({ productId, quantity })
    });
    if (!res.ok) throw new Error("Failed to update cart");
    return res.json();
  }

  async function migrateCart() {
    const headers = await getHeaders(true);
    const res = await fetch(CONFIG.CART_API_URL + "/cart/migrate", {
      method: "POST",
      headers,
      credentials: "include"
    });
    if (!res.ok) throw new Error("Failed to migrate cart");
    return res.json();
  }

  async function checkoutCart() {
    const headers = await getHeaders(true);
    const res = await fetch(CONFIG.CART_API_URL + "/cart/checkout", {
      method: "POST",
      headers,
      credentials: "include"
    });
    if (!res.ok) throw new Error("Failed to checkout");
    return res.json();
  }

  async function askAssistant(message, sessionId = null) {
    const headers = await getHeaders(true);
    const res = await fetch(CONFIG.ASSISTANT_API_URL + "/assistant", {
      method: "POST",
      headers,
      body: JSON.stringify({ message, sessionId })
    });
    if (!res.ok) throw new Error("Assistant unavailable");
    return res.json();
  }

  return {
    getProducts,
    getCart,
    addToCart,
    updateCart,
    migrateCart,
    checkoutCart,
    askAssistant
  };
})();
