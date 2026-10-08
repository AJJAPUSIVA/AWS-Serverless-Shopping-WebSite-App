import importlib.util
import os
import pathlib
import sys
import types
import unittest
from unittest.mock import MagicMock, patch


MODULE_PATH = pathlib.Path(__file__).parents[1] / "action_handler.py"


class FakeRepositoryError(RuntimeError):
    pass


class ActionHandlerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.environment = patch.dict(
            os.environ,
            {"SESSION_TABLE_NAME": "session-table", "AWS_DEFAULT_REGION": "us-east-1"},
        )
        cls.environment.start()

        boto3_module = types.ModuleType("boto3")
        boto3_module.resource = MagicMock()
        cls.repository = types.ModuleType("mysql_repository")
        for name in ("EmptyCartError", "InventoryError", "NotFoundError"):
            setattr(cls.repository, name, FakeRepositoryError)
        for name in (
            "add_cart_item",
            "cart_total",
            "checkout_cart",
            "get_inventory",
            "list_products",
            "order_history",
            "sales_summary",
            "set_cart_item_quantity",
            "user_owner_key",
        ):
            setattr(cls.repository, name, MagicMock())
        cls.repository.user_owner_key.side_effect = lambda value: f"user:{value}"

        cls.modules = patch.dict(
            sys.modules,
            {"boto3": boto3_module, "mysql_repository": cls.repository},
        )
        cls.modules.start()
        spec = importlib.util.spec_from_file_location("action_handler", MODULE_PATH)
        cls.module = importlib.util.module_from_spec(spec)
        sys.modules["action_handler"] = cls.module
        spec.loader.exec_module(cls.module)

    @classmethod
    def tearDownClass(cls):
        cls.modules.stop()
        cls.environment.stop()
        sys.modules.pop("action_handler", None)

    def setUp(self):
        for value in vars(self.repository).values():
            if isinstance(value, MagicMock):
                value.reset_mock()
        self.repository.user_owner_key.side_effect = lambda value: f"user:{value}"

    def test_positive_quantity_rejects_zero(self):
        with self.assertRaises(self.module.ToolInputError):
            self.module._quantity("0")

    def test_search_uses_typed_repository_filters(self):
        self.repository.list_products.return_value = [
            {
                "productId": "1",
                "name": "Apple",
                "category": "fruit",
                "description": "Fresh",
                "price": 125,
                "availableQuantity": 8,
            }
        ]
        result = self.module.search_products(
            {"category": "fruit", "max_price": "2.00"}, "user-sub"
        )
        self.repository.list_products.assert_called_once_with(
            query=None, category="fruit", max_price_cents=200, limit=8
        )
        self.assertEqual(result["products"][0]["price"], 1.25)

    def test_checkout_preview_does_not_place_order(self):
        self.repository.cart_total.return_value = {"products": [], "total": 0.0}
        result = self.module.preview_checkout({}, "user-sub")
        self.repository.checkout_cart.assert_not_called()
        self.assertIn("preview only", result["message"].lower())

    def test_confirm_checkout_uses_customer_identity(self):
        self.repository.checkout_cart.return_value = {"orderId": "order-1"}
        result = self.module.confirm_checkout({}, "customer-sub")
        self.repository.checkout_cart.assert_called_once_with("customer-sub")
        self.assertEqual(result["order"]["orderId"], "order-1")


if __name__ == "__main__":
    unittest.main()
