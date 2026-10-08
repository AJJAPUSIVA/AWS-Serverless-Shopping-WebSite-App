CREATE TABLE IF NOT EXISTS customers (
    customer_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    cognito_sub VARCHAR(128) NOT NULL,
    email VARCHAR(320) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (customer_id),
    UNIQUE KEY uq_customers_cognito_sub (cognito_sub)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS products (
    product_id CHAR(36) NOT NULL,
    name VARCHAR(160) NOT NULL,
    category VARCHAR(80) NOT NULL,
    description VARCHAR(1000) NOT NULL,
    price_cents INT UNSIGNED NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (product_id),
    KEY idx_products_category_price (category, price_cents),
    FULLTEXT KEY ft_products_name_description (name, description),
    CONSTRAINT chk_products_price CHECK (price_cents >= 0)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS product_tags (
    product_id CHAR(36) NOT NULL,
    tag VARCHAR(80) NOT NULL,
    PRIMARY KEY (product_id, tag),
    KEY idx_product_tags_tag (tag),
    CONSTRAINT fk_product_tags_product
        FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS inventory (
    product_id CHAR(36) NOT NULL,
    available_quantity INT UNSIGNED NOT NULL DEFAULT 0,
    reorder_level INT UNSIGNED NOT NULL DEFAULT 10,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (product_id),
    CONSTRAINT fk_inventory_product
        FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE CASCADE,
    CONSTRAINT chk_inventory_available CHECK (available_quantity >= 0)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS carts (
    cart_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    owner_key VARCHAR(180) NOT NULL,
    customer_id BIGINT UNSIGNED NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (cart_id),
    UNIQUE KEY uq_carts_owner_key (owner_key),
    KEY idx_carts_customer (customer_id),
    CONSTRAINT fk_carts_customer
        FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS cart_items (
    cart_id BIGINT UNSIGNED NOT NULL,
    product_id CHAR(36) NOT NULL,
    quantity SMALLINT UNSIGNED NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (cart_id, product_id),
    KEY idx_cart_items_product (product_id),
    CONSTRAINT fk_cart_items_cart
        FOREIGN KEY (cart_id) REFERENCES carts(cart_id) ON DELETE CASCADE,
    CONSTRAINT fk_cart_items_product
        FOREIGN KEY (product_id) REFERENCES products(product_id),
    CONSTRAINT chk_cart_items_quantity CHECK (quantity BETWEEN 1 AND 99)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS orders (
    order_id CHAR(36) NOT NULL,
    customer_id BIGINT UNSIGNED NOT NULL,
    status ENUM('PLACED', 'PAID', 'FULFILLED', 'CANCELLED') NOT NULL DEFAULT 'PLACED',
    total_cents INT UNSIGNED NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (order_id),
    KEY idx_orders_customer_created (customer_id, created_at),
    CONSTRAINT fk_orders_customer
        FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS order_items (
    order_id CHAR(36) NOT NULL,
    product_id CHAR(36) NOT NULL,
    product_name VARCHAR(160) NOT NULL,
    unit_price_cents INT UNSIGNED NOT NULL,
    quantity SMALLINT UNSIGNED NOT NULL,
    PRIMARY KEY (order_id, product_id),
    CONSTRAINT fk_order_items_order
        FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
    CONSTRAINT fk_order_items_product
        FOREIGN KEY (product_id) REFERENCES products(product_id),
    CONSTRAINT chk_order_items_quantity CHECK (quantity BETWEEN 1 AND 99)
) ENGINE=InnoDB;

INSERT INTO products (product_id, name, category, description, price_cents) VALUES
('4c1fadaa-213a-4ea8-aa32-58c217604e3c', 'Packaged strawberries', 'fruit', 'Fresh strawberries in a convenient recyclable package.', 716),
('d2580eff-d105-45a5-9b21-ba61995bc6da', 'Candied prunes', 'sweets', 'Sweet candied prunes for snacks and desserts.', 335),
('a6dd7187-40b6-4cb5-b73c-aecd655c6d9a', 'Fresh prunes', 'fruit', 'Fresh seasonal prunes sold by the package.', 202),
('c0fbcc6b-7a70-41ac-aac4-f8fd237dc62e', 'Packaged tomatoes', 'vegetable', 'Ripe tomatoes packed for easy storage.', 397),
('cb40c919-033a-47d6-8d00-1d73e2df20fe', 'Fresh tomatoes', 'vegetable', 'Fresh tomatoes suitable for salads and cooking.', 244),
('12929eb9-3eb7-4217-99e4-1a39c39217b6', 'Fresh lettuce', 'vegetable', 'Crisp green lettuce harvested fresh.', 251),
('9fd9ef32-493f-4188-99f5-3aa809aa4fa9', 'Packaged steak', 'meat', 'Premium packaged steak ready for cooking.', 894),
('8c843a54-27d7-477c-81b3-c21db12ed1c9', 'Chocolate cake', 'sweets', 'Rich chocolate cake for sharing.', 522)
ON DUPLICATE KEY UPDATE
    name = VALUES(name),
    category = VALUES(category),
    description = VALUES(description),
    price_cents = VALUES(price_cents),
    active = TRUE;

INSERT INTO inventory (product_id, available_quantity, reorder_level)
SELECT product_id, 100, 10 FROM products
ON DUPLICATE KEY UPDATE reorder_level = VALUES(reorder_level);

INSERT IGNORE INTO product_tags (product_id, tag) VALUES
('4c1fadaa-213a-4ea8-aa32-58c217604e3c', 'fresh'),
('4c1fadaa-213a-4ea8-aa32-58c217604e3c', 'breakfast'),
('d2580eff-d105-45a5-9b21-ba61995bc6da', 'snack'),
('a6dd7187-40b6-4cb5-b73c-aecd655c6d9a', 'fresh'),
('c0fbcc6b-7a70-41ac-aac4-f8fd237dc62e', 'salad'),
('cb40c919-033a-47d6-8d00-1d73e2df20fe', 'salad'),
('12929eb9-3eb7-4217-99e4-1a39c39217b6', 'salad'),
('9fd9ef32-493f-4188-99f5-3aa809aa4fa9', 'protein'),
('8c843a54-27d7-477c-81b3-c21db12ed1c9', 'dessert');
