"""Safe, parameterized MySQL access for the commerce services.

The Bedrock agent and API handlers call these typed functions. They never accept
SQL text, table names, or column names from a user or model.
"""

import contextlib
import os
import uuid

import boto3
import pymysql
from pymysql.cursors import DictCursor


class RepositoryError(RuntimeError):
    pass


class NotFoundError(RepositoryError):
    pass


class InventoryError(RepositoryError):
    pass


class EmptyCartError(RepositoryError):
    pass


_connection = None


def _new_connection():
    host = os.environ["DB_HOST"]
    port = int(os.environ.get("DB_PORT", "3306"))
    user = os.environ["DB_USER"]
    password = os.environ.get("MYSQL_PASSWORD")
    options = {}
    if password is None:
        password = boto3.client("rds").generate_db_auth_token(
            DBHostname=host,
            Port=port,
            DBUsername=user,
            Region=os.environ["AWS_REGION"],
        )
        options.update(
            ssl={"ca": "/etc/pki/tls/certs/ca-bundle.crt"},
            ssl_verify_cert=True,
            ssl_verify_identity=True,
        )

    return pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=os.environ["DB_NAME"],
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=True,
        connect_timeout=5,
        read_timeout=5,
        write_timeout=5,
        **options,
    )


def connection():
    global _connection
    if _connection is None:
        _connection = _new_connection()
    else:
        _connection.ping(reconnect=True)
    return _connection


def close_connection():
    global _connection
    if _connection is not None:
        _connection.close()
        _connection = None


@contextlib.contextmanager
def transaction():
    db = connection()
    db.begin()
    try:
        with db.cursor() as cursor:
            yield cursor
        db.commit()
    except Exception:
        db.rollback()
        raise


def user_owner_key(cognito_sub):
    if not cognito_sub:
        raise ValueError("A Cognito subject is required")
    return f"user:{cognito_sub}"


def anonymous_owner_key(cart_id):
    if not cart_id:
        raise ValueError("A cart identifier is required")
    return f"cart:{cart_id}"


def _tags(value):
    return value.split("\x1f") if value else []


def _product(row):
    return {
        "productId": row["product_id"],
        "name": row["name"],
        "category": row["category"],
        "description": row["description"],
        "price": int(row["price_cents"]),
        "availableQuantity": int(row.get("available_quantity") or 0),
        "tags": _tags(row.get("tags")),
    }


_PRODUCT_SELECT = """
    SELECT p.product_id, p.name, p.category, p.description, p.price_cents,
           i.available_quantity,
           GROUP_CONCAT(DISTINCT pt.tag ORDER BY pt.tag SEPARATOR '\x1f') AS tags
      FROM products p
      JOIN inventory i ON i.product_id = p.product_id
 LEFT JOIN product_tags pt ON pt.product_id = p.product_id
"""


def list_products(query=None, category=None, max_price_cents=None, limit=100):
    clauses = ["p.active = TRUE"]
    values = []
    if query:
        clauses.append(
            "(LOWER(p.name) LIKE %s OR LOWER(p.description) LIKE %s "
            "OR EXISTS (SELECT 1 FROM product_tags x "
            "WHERE x.product_id = p.product_id AND LOWER(x.tag) LIKE %s))"
        )
        pattern = f"%{query.lower()}%"
        values.extend([pattern, pattern, pattern])
    if category:
        clauses.append("LOWER(p.category) = %s")
        values.append(category.lower())
    if max_price_cents is not None:
        clauses.append("p.price_cents <= %s")
        values.append(int(max_price_cents))

    limit = min(max(int(limit), 1), 100)
    sql = (
        _PRODUCT_SELECT
        + " WHERE "
        + " AND ".join(clauses)
        + " GROUP BY p.product_id, p.name, p.category, p.description, "
        "p.price_cents, i.available_quantity"
        + " ORDER BY p.price_cents, p.name LIMIT %s"
    )
    values.append(limit)
    with connection().cursor() as cursor:
        cursor.execute(sql, values)
        return [_product(row) for row in cursor.fetchall()]


def get_product(product_id):
    sql = (
        _PRODUCT_SELECT
        + " WHERE p.product_id = %s AND p.active = TRUE"
        + " GROUP BY p.product_id, p.name, p.category, p.description, "
        "p.price_cents, i.available_quantity"
    )
    with connection().cursor() as cursor:
        cursor.execute(sql, (product_id,))
        row = cursor.fetchone()
    if not row:
        raise NotFoundError("Product not found")
    return _product(row)


def get_inventory(product_id):
    with connection().cursor() as cursor:
        cursor.execute(
            """
            SELECT p.product_id, p.name, i.available_quantity, i.reorder_level,
                   (i.available_quantity <= i.reorder_level) AS low_stock
              FROM products p
              JOIN inventory i ON i.product_id = p.product_id
             WHERE p.product_id = %s AND p.active = TRUE
            """,
            (product_id,),
        )
        row = cursor.fetchone()
    if not row:
        raise NotFoundError("Product not found")
    return {
        "productId": row["product_id"],
        "name": row["name"],
        "availableQuantity": int(row["available_quantity"]),
        "lowStock": bool(row["low_stock"]),
    }


def _ensure_customer(cursor, cognito_sub):
    cursor.execute(
        """
        INSERT INTO customers (cognito_sub) VALUES (%s)
        ON DUPLICATE KEY UPDATE customer_id = LAST_INSERT_ID(customer_id)
        """,
        (cognito_sub,),
    )
    customer_id = cursor.lastrowid
    if not customer_id:
        cursor.execute(
            "SELECT customer_id FROM customers WHERE cognito_sub = %s",
            (cognito_sub,),
        )
        customer_id = cursor.fetchone()["customer_id"]
    return customer_id


def _ensure_cart(cursor, owner_key, customer_id=None):
    cursor.execute(
        """
        INSERT INTO carts (owner_key, customer_id) VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE
            cart_id = LAST_INSERT_ID(cart_id),
            customer_id = COALESCE(VALUES(customer_id), customer_id),
            updated_at = CURRENT_TIMESTAMP
        """,
        (owner_key, customer_id),
    )
    cart_id = cursor.lastrowid
    if not cart_id:
        cursor.execute("SELECT cart_id FROM carts WHERE owner_key = %s", (owner_key,))
        cart_id = cursor.fetchone()["cart_id"]
    return cart_id


def list_cart(owner_key):
    with connection().cursor() as cursor:
        cursor.execute(
            """
            SELECT p.product_id, p.name, p.category, p.description, p.price_cents,
                   ci.quantity
              FROM carts c
              JOIN cart_items ci ON ci.cart_id = c.cart_id
              JOIN products p ON p.product_id = ci.product_id
             WHERE c.owner_key = %s
             ORDER BY p.name
            """,
            (owner_key,),
        )
        rows = cursor.fetchall()
    return [
        {
            "sk": row["product_id"],
            "quantity": int(row["quantity"]),
            "productDetail": {
                "productId": row["product_id"],
                "name": row["name"],
                "category": row["category"],
                "description": row["description"],
                "price": int(row["price_cents"]),
            },
        }
        for row in rows
    ]


def _locked_product(cursor, product_id):
    cursor.execute(
        """
        SELECT p.product_id, p.name, p.price_cents, i.available_quantity
          FROM products p
          JOIN inventory i ON i.product_id = p.product_id
         WHERE p.product_id = %s AND p.active = TRUE
         FOR UPDATE
        """,
        (product_id,),
    )
    row = cursor.fetchone()
    if not row:
        raise NotFoundError("Product not found")
    return row


def add_cart_item(owner_key, product_id, quantity, customer_sub=None):
    quantity = int(quantity)
    if quantity == 0 or quantity < -99 or quantity > 99:
        raise ValueError("Quantity change must be between -99 and 99 and cannot be zero")
    with transaction() as cursor:
        product = _locked_product(cursor, product_id)
        customer_id = _ensure_customer(cursor, customer_sub) if customer_sub else None
        cart_id = _ensure_cart(cursor, owner_key, customer_id)
        cursor.execute(
            "SELECT quantity FROM cart_items WHERE cart_id = %s AND product_id = %s FOR UPDATE",
            (cart_id, product_id),
        )
        existing = cursor.fetchone()
        new_quantity = int(existing["quantity"] if existing else 0) + quantity
        if new_quantity < 0:
            raise ValueError("Cart quantity cannot be negative")
        if new_quantity > 99:
            raise ValueError("Cart quantity cannot exceed 99")
        if new_quantity > int(product["available_quantity"]):
            raise InventoryError("Requested quantity is not available")
        if new_quantity == 0:
            cursor.execute(
                "DELETE FROM cart_items WHERE cart_id = %s AND product_id = %s",
                (cart_id, product_id),
            )
        else:
            cursor.execute(
                """
                INSERT INTO cart_items (cart_id, product_id, quantity) VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE quantity = VALUES(quantity), updated_at = CURRENT_TIMESTAMP
                """,
                (cart_id, product_id, new_quantity),
            )
    return {"productId": product_id, "quantity": new_quantity, "name": product["name"]}


def set_cart_item_quantity(owner_key, product_id, quantity, customer_sub=None):
    quantity = int(quantity)
    if quantity < 0 or quantity > 99:
        raise ValueError("Quantity must be between 0 and 99")
    with transaction() as cursor:
        product = _locked_product(cursor, product_id)
        if quantity > int(product["available_quantity"]):
            raise InventoryError("Requested quantity is not available")
        customer_id = _ensure_customer(cursor, customer_sub) if customer_sub else None
        cart_id = _ensure_cart(cursor, owner_key, customer_id)
        if quantity == 0:
            cursor.execute(
                "DELETE FROM cart_items WHERE cart_id = %s AND product_id = %s",
                (cart_id, product_id),
            )
        else:
            cursor.execute(
                """
                INSERT INTO cart_items (cart_id, product_id, quantity) VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE quantity = VALUES(quantity), updated_at = CURRENT_TIMESTAMP
                """,
                (cart_id, product_id, quantity),
            )
    return {"productId": product_id, "quantity": quantity, "name": product["name"]}


def migrate_cart(anonymous_key, cognito_sub):
    user_key = user_owner_key(cognito_sub)
    with transaction() as cursor:
        customer_id = _ensure_customer(cursor, cognito_sub)
        user_cart_id = _ensure_cart(cursor, user_key, customer_id)
        cursor.execute(
            "SELECT cart_id FROM carts WHERE owner_key = %s FOR UPDATE", (anonymous_key,)
        )
        anonymous_cart = cursor.fetchone()
        if not anonymous_cart:
            return list_cart(user_key)
        anonymous_cart_id = anonymous_cart["cart_id"]
        cursor.execute(
            "SELECT product_id, quantity FROM cart_items WHERE cart_id = %s FOR UPDATE",
            (anonymous_cart_id,),
        )
        for item in cursor.fetchall():
            product = _locked_product(cursor, item["product_id"])
            cursor.execute(
                "SELECT quantity FROM cart_items WHERE cart_id = %s AND product_id = %s FOR UPDATE",
                (user_cart_id, item["product_id"]),
            )
            existing = cursor.fetchone()
            quantity = int(item["quantity"]) + int(existing["quantity"] if existing else 0)
            if quantity > min(99, int(product["available_quantity"])):
                raise InventoryError(f"Not enough inventory for {product['name']}")
            cursor.execute(
                """
                INSERT INTO cart_items (cart_id, product_id, quantity) VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE quantity = VALUES(quantity), updated_at = CURRENT_TIMESTAMP
                """,
                (user_cart_id, item["product_id"], quantity),
            )
        cursor.execute("DELETE FROM carts WHERE cart_id = %s", (anonymous_cart_id,))
    return list_cart(user_key)


def cart_total(owner_key):
    items = list_cart(owner_key)
    total_cents = sum(item["productDetail"]["price"] * item["quantity"] for item in items)
    return {"products": items, "totalCents": total_cents, "total": total_cents / 100}


def checkout_cart(cognito_sub):
    owner_key = user_owner_key(cognito_sub)
    order_id = str(uuid.uuid4())
    with transaction() as cursor:
        customer_id = _ensure_customer(cursor, cognito_sub)
        cart_id = _ensure_cart(cursor, owner_key, customer_id)
        cursor.execute(
            """
            SELECT ci.product_id, ci.quantity, p.name, p.price_cents,
                   i.available_quantity
              FROM cart_items ci
              JOIN products p ON p.product_id = ci.product_id
              JOIN inventory i ON i.product_id = ci.product_id
             WHERE ci.cart_id = %s
             ORDER BY ci.product_id
             FOR UPDATE
            """,
            (cart_id,),
        )
        items = cursor.fetchall()
        if not items:
            raise EmptyCartError("The cart is empty")
        for item in items:
            if int(item["quantity"]) > int(item["available_quantity"]):
                raise InventoryError(f"Not enough inventory for {item['name']}")
        total_cents = sum(int(item["price_cents"]) * int(item["quantity"]) for item in items)
        cursor.execute(
            "INSERT INTO orders (order_id, customer_id, status, total_cents) VALUES (%s, %s, 'PLACED', %s)",
            (order_id, customer_id, total_cents),
        )
        for item in items:
            cursor.execute(
                """
                INSERT INTO order_items
                    (order_id, product_id, product_name, unit_price_cents, quantity)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    order_id,
                    item["product_id"],
                    item["name"],
                    item["price_cents"],
                    item["quantity"],
                ),
            )
            cursor.execute(
                "UPDATE inventory SET available_quantity = available_quantity - %s WHERE product_id = %s",
                (item["quantity"], item["product_id"]),
            )
        cursor.execute("DELETE FROM cart_items WHERE cart_id = %s", (cart_id,))
    return {
        "orderId": order_id,
        "status": "PLACED",
        "itemCount": sum(int(item["quantity"]) for item in items),
        "totalCents": total_cents,
        "total": total_cents / 100,
    }


def order_history(cognito_sub, limit=10):
    limit = min(max(int(limit), 1), 20)
    with connection().cursor() as cursor:
        cursor.execute(
            """
            SELECT o.order_id, o.status, o.total_cents, o.created_at,
                   SUM(oi.quantity) AS item_count
              FROM customers c
              JOIN orders o ON o.customer_id = c.customer_id
              JOIN order_items oi ON oi.order_id = o.order_id
             WHERE c.cognito_sub = %s
             GROUP BY o.order_id, o.status, o.total_cents, o.created_at
             ORDER BY o.created_at DESC
             LIMIT %s
            """,
            (cognito_sub, limit),
        )
        rows = cursor.fetchall()
    return [
        {
            "orderId": row["order_id"],
            "status": row["status"],
            "total": int(row["total_cents"]) / 100,
            "itemCount": int(row["item_count"]),
            "createdAt": row["created_at"].isoformat(),
        }
        for row in rows
    ]


def sales_summary(limit=5):
    limit = min(max(int(limit), 1), 10)
    with connection().cursor() as cursor:
        cursor.execute(
            """
            SELECT oi.product_id, oi.product_name,
                   SUM(oi.quantity) AS units_sold,
                   SUM(oi.quantity * oi.unit_price_cents) AS revenue_cents
              FROM order_items oi
              JOIN orders o ON o.order_id = oi.order_id
             WHERE o.status <> 'CANCELLED'
             GROUP BY oi.product_id, oi.product_name
             ORDER BY units_sold DESC, revenue_cents DESC
             LIMIT %s
            """,
            (limit,),
        )
        rows = cursor.fetchall()
    return [
        {
            "productId": row["product_id"],
            "name": row["product_name"],
            "unitsSold": int(row["units_sold"]),
            "revenue": int(row["revenue_cents"]) / 100,
        }
        for row in rows
    ]


def cart_quantity_for_product(product_id):
    with connection().cursor() as cursor:
        cursor.execute(
            "SELECT COALESCE(SUM(quantity), 0) AS quantity FROM cart_items WHERE product_id = %s",
            (product_id,),
        )
        return int(cursor.fetchone()["quantity"])
