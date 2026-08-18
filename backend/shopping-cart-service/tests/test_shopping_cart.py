"""
Unit tests for shopping cart service Lambda handlers.
"""
import json
import os
import sys
import types
import unittest
from decimal import Decimal
from unittest.mock import MagicMock, patch

# Add paths for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "layers"))


class TestSharedModule(unittest.TestCase):
    """Test the shared utility layer."""

    def setUp(self):
        os.environ.setdefault("ALLOWED_ORIGIN", "http://localhost:8080")
        os.environ.setdefault("AWS_REGION", "us-east-1")
        os.environ.setdefault("USERPOOL_ID", "us-east-1_TestPool")

        # Mock cognitojwt and aws_lambda_powertools before import
        self.mock_cognitojwt = types.ModuleType("cognitojwt")
        self.mock_cognitojwt.decode = MagicMock(return_value={"sub": "user-abc-123"})
        self.mock_cognitojwt.CognitoJWTException = Exception

        self.mock_powertools_tracer = MagicMock()
        self.mock_powertools_tracer.capture_method = lambda f: f

        powertools_module = types.ModuleType("aws_lambda_powertools")
        powertools_module.Tracer = MagicMock(return_value=self.mock_powertools_tracer)

        self.patches = patch.dict(sys.modules, {
            "cognitojwt": self.mock_cognitojwt,
            "aws_lambda_powertools": powertools_module,
        })
        self.patches.start()

        # Force reload shared
        if "shared" in sys.modules:
            del sys.modules["shared"]
        import shared
        self.shared = shared

    def tearDown(self):
        self.patches.stop()
        if "shared" in sys.modules:
            del sys.modules["shared"]

    def test_headers_contain_cors_fields(self):
        """CORS headers must include Allow-Origin and Allow-Credentials."""
        self.assertEqual(self.shared.HEADERS["Access-Control-Allow-Credentials"], True)
        self.assertEqual(
            self.shared.HEADERS["Access-Control-Allow-Origin"], "http://localhost:8080"
        )

    def test_handle_decimal_type_integer(self):
        """Decimal values that are integers should be returned as int."""
        result = self.shared.handle_decimal_type(Decimal("5"))
        self.assertEqual(result, 5)
        self.assertIsInstance(result, int)

    def test_handle_decimal_type_float(self):
        """Decimal values with fractional parts should be returned as float."""
        result = self.shared.handle_decimal_type(Decimal("3.99"))
        self.assertAlmostEqual(result, 3.99)
        self.assertIsInstance(result, float)

    def test_handle_decimal_type_raises_for_non_decimal(self):
        """Non-Decimal types should raise TypeError."""
        with self.assertRaises(TypeError):
            self.shared.handle_decimal_type("not a decimal")

    def test_generate_ttl_returns_future_timestamp(self):
        """TTL should be a future epoch timestamp."""
        import time
        ttl = self.shared.generate_ttl(days=1)
        self.assertGreater(ttl, int(time.time()))

    def test_generate_ttl_7_days_greater_than_1_day(self):
        """7-day TTL should be greater than 1-day TTL."""
        ttl_1 = self.shared.generate_ttl(days=1)
        ttl_7 = self.shared.generate_ttl(days=7)
        self.assertGreater(ttl_7, ttl_1)

    def test_get_cart_id_generates_uuid_when_no_cookie(self):
        """When no cookie is present, a new UUID should be generated."""
        cart_id, generated = self.shared.get_cart_id({})
        self.assertTrue(generated)
        self.assertEqual(len(cart_id), 36)  # UUID format

    def test_get_cart_id_reads_existing_cookie(self):
        """When cartId cookie exists, it should be read."""
        headers = {"cookie": "cartId=existing-cart-123"}
        cart_id, generated = self.shared.get_cart_id(headers)
        self.assertFalse(generated)
        self.assertEqual(cart_id, "existing-cart-123")

    def test_get_user_sub_valid_token(self):
        """Valid JWT should return the user sub."""
        result = self.shared.get_user_sub("valid-token")
        self.assertEqual(result, "user-abc-123")

    def test_get_user_sub_invalid_token(self):
        """Invalid JWT should return None."""
        self.mock_cognitojwt.decode.side_effect = Exception("Invalid token")
        result = self.shared.get_user_sub("bad-token")
        self.assertIsNone(result)

    def test_get_headers_includes_set_cookie(self):
        """Response headers should include Set-Cookie with cartId."""
        headers = self.shared.get_headers("test-cart-id")
        self.assertIn("Set-Cookie", headers)
        self.assertIn("cartId=test-cart-id", headers["Set-Cookie"])
        self.assertIn("httponly", headers["Set-Cookie"].lower())
        self.assertIn("secure", headers["Set-Cookie"].lower())


class TestProductMockService(unittest.TestCase):
    """Test the product mock service handlers."""

    def setUp(self):
        os.environ.setdefault("ALLOWED_ORIGIN", "http://localhost:8080")
        os.environ.setdefault("POWERTOOLS_SERVICE_NAME", "test")
        os.environ.setdefault("POWERTOOLS_METRICS_NAMESPACE", "test")

    def test_product_list_json_is_valid(self):
        """product_list.json should be valid JSON with products array."""
        product_list_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "product-mock-service", "product_list.json"
        )
        with open(product_list_path, "r") as f:
            data = json.load(f)

        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)

        # Each product should have required fields
        for product in data:
            self.assertIn("productId", product)
            self.assertIn("name", product)
            self.assertIn("price", product)
            self.assertIn("category", product)
            self.assertIsInstance(product["price"], int)
            self.assertGreater(product["price"], 0)


if __name__ == "__main__":
    unittest.main()
