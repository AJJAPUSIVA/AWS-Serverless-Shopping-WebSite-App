import importlib.util
import json
import os
import pathlib
import sys
import types
import unittest
from unittest.mock import MagicMock, patch


MODULE_PATH = pathlib.Path(__file__).parents[1] / "chat_handler.py"


class ChatHandlerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        environment = {
            "ALLOWED_ORIGIN": "https://shop.example.test",
            "AGENT_ID": "ABCDEFGHIJ",
            "AGENT_ALIAS_ID": "KLMNOPQRST",
            "SESSION_TABLE_NAME": "session-table",
            "AWS_DEFAULT_REGION": "us-east-1",
        }
        cls.environment = patch.dict(os.environ, environment)
        cls.environment.start()
        boto3_module = types.ModuleType("boto3")
        boto3_module.client = MagicMock(return_value=MagicMock())
        boto3_module.resource = MagicMock()
        boto3_module.resource.return_value.Table.return_value = MagicMock()
        cls.modules = patch.dict(sys.modules, {"boto3": boto3_module})
        cls.modules.start()
        spec = importlib.util.spec_from_file_location("chat_handler", MODULE_PATH)
        cls.module = importlib.util.module_from_spec(spec)
        sys.modules["chat_handler"] = cls.module
        spec.loader.exec_module(cls.module)

    @classmethod
    def tearDownClass(cls):
        cls.modules.stop()
        cls.environment.stop()
        sys.modules.pop("chat_handler", None)

    def test_rejects_anonymous_requests(self):
        response = self.module.lambda_handler({"body": "{}"}, None)
        self.assertEqual(response["statusCode"], 401)

    def test_validates_message_length(self):
        event = {
            "requestContext": {"authorizer": {"claims": {"sub": "user-123"}}},
            "body": json.dumps({"message": ""}),
        }
        response = self.module.lambda_handler(event, None)
        self.assertEqual(response["statusCode"], 400)


if __name__ == "__main__":
    unittest.main()
