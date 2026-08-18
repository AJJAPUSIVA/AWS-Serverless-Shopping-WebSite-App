import importlib.util
import os
import pathlib
import sys
import types
import unittest
from unittest.mock import MagicMock, patch


MODULE_PATH = pathlib.Path(__file__).parents[1] / "action_handler.py"


class ActionHandlerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        environment = {
            "PRODUCT_SERVICE_URL": "https://products.example.test",
            "CART_TABLE_NAME": "cart-table",
            "SESSION_TABLE_NAME": "session-table",
            "AWS_DEFAULT_REGION": "us-east-1",
        }
        cls.environment = patch.dict(os.environ, environment)
        cls.environment.start()
        boto3_module = types.ModuleType("boto3")
        boto3_module.resource = MagicMock()
        boto3_module.resource.return_value.Table.return_value = MagicMock()
        dynamodb_module = types.ModuleType("boto3.dynamodb")
        conditions_module = types.ModuleType("boto3.dynamodb.conditions")
        conditions_module.Key = MagicMock()
        cls.modules = patch.dict(
            sys.modules,
            {
                "boto3": boto3_module,
                "boto3.dynamodb": dynamodb_module,
                "boto3.dynamodb.conditions": conditions_module,
            },
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

    def test_positive_quantity_rejects_zero(self):
        with self.assertRaises(self.module.ToolInputError):
            self.module._positive_quantity("0")

    def test_search_filters_by_category_and_price(self):
        products = {
            "products": [
                {"productId": "1", "name": "Apple", "category": "fruit", "price": 125},
                {"productId": "2", "name": "Steak", "category": "meat", "price": 900},
            ]
        }
        with patch.object(self.module, "_fetch_json", return_value=products):
            result = self.module.search_products(
                {"category": "fruit", "max_price": "2.00"}, "user#123"
            )
        self.assertEqual(result["matchCount"], 1)
        self.assertEqual(result["products"][0]["productId"], "1")

    def test_checkout_preview_does_not_delete_items(self):
        with patch.object(
            self.module,
            "_cart_summary",
            return_value={"products": [], "total": 0.0},
        ):
            result = self.module.preview_checkout({}, "user#123")
        self.assertIn("preview only", result["message"].lower())


if __name__ == "__main__":
    unittest.main()
