import os
import pathlib
import sys
import unittest


MYSQL_INTEGRATION = os.environ.get("MYSQL_INTEGRATION") == "1"
if MYSQL_INTEGRATION:
    LAYERS = pathlib.Path(__file__).parents[1] / "layers"
    sys.path.insert(0, str(LAYERS))
    import mysql_repository as repository  # noqa: E402


PRODUCT_ID = "4c1fadaa-213a-4ea8-aa32-58c217604e3c"
CUSTOMER_SUB = "ci-integration-customer"


@unittest.skipUnless(MYSQL_INTEGRATION, "MySQL is not configured")
class MySqlRepositoryIntegrationTests(unittest.TestCase):
    def setUp(self):
        self._clean_customer()
        with repository.transaction() as cursor:
            cursor.execute(
                "UPDATE inventory SET available_quantity = 100 WHERE product_id = %s",
                (PRODUCT_ID,),
            )

    def tearDown(self):
        self._clean_customer()
        with repository.transaction() as cursor:
            cursor.execute(
                "UPDATE inventory SET available_quantity = 100 WHERE product_id = %s",
                (PRODUCT_ID,),
            )

    @classmethod
    def tearDownClass(cls):
        repository.close_connection()

    def _clean_customer(self):
        owner_key = repository.user_owner_key(CUSTOMER_SUB)
        with repository.transaction() as cursor:
            cursor.execute(
                "DELETE oi FROM order_items oi JOIN orders o ON o.order_id = oi.order_id "
                "JOIN customers c ON c.customer_id = o.customer_id WHERE c.cognito_sub = %s",
                (CUSTOMER_SUB,),
            )
            cursor.execute(
                "DELETE o FROM orders o JOIN customers c ON c.customer_id = o.customer_id "
                "WHERE c.cognito_sub = %s",
                (CUSTOMER_SUB,),
            )
            cursor.execute("DELETE FROM carts WHERE owner_key = %s", (owner_key,))
            cursor.execute("DELETE FROM customers WHERE cognito_sub = %s", (CUSTOMER_SUB,))

    def test_seeded_catalog_can_be_filtered(self):
        products = repository.list_products(category="fruit", max_price_cents=800)
        self.assertGreaterEqual(len(products), 1)
        self.assertTrue(all(product["category"] == "fruit" for product in products))

    def test_search_input_is_data_not_sql(self):
        products = repository.list_products(query="%' OR 1=1; DROP TABLE products; --")
        self.assertEqual(products, [])
        self.assertIsNotNone(repository.get_product(PRODUCT_ID))

    def test_cart_checkout_creates_order_and_decrements_inventory(self):
        owner_key = repository.user_owner_key(CUSTOMER_SUB)
        before = repository.get_inventory(PRODUCT_ID)["availableQuantity"]
        repository.add_cart_item(
            owner_key, PRODUCT_ID, 2, customer_sub=CUSTOMER_SUB
        )
        cart = repository.cart_total(owner_key)
        self.assertEqual(cart["products"][0]["quantity"], 2)

        order = repository.checkout_cart(CUSTOMER_SUB)
        after = repository.get_inventory(PRODUCT_ID)["availableQuantity"]
        history = repository.order_history(CUSTOMER_SUB)

        self.assertEqual(order["status"], "PLACED")
        self.assertEqual(after, before - 2)
        self.assertEqual(history[0]["orderId"], order["orderId"])
        self.assertEqual(repository.cart_total(owner_key)["products"], [])


if __name__ == "__main__":
    unittest.main()
