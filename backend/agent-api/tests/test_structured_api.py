import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


AGENT_API_DIRECTORY = Path(__file__).parents[1]
sys.path.insert(0, str(AGENT_API_DIRECTORY))

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AGENT_ID", "ABCDEFGHIJ")
os.environ.setdefault("AGENT_ALIAS_ID", "KLMNOPQRST")
os.environ.setdefault("SESSION_TABLE_NAME", "session-table")
os.environ.setdefault("FOUNDATION_MODEL_ID", "amazon.nova-lite-v1:0")

import app  # noqa: E402
import service  # noqa: E402
from knowledge import _retriever, retrieve_policy_context  # noqa: E402
from schemas import (  # noqa: E402
    AssistantRequest,
    ResponseType,
    StructuredAssistantPayload,
)
from session_store import normalize_session_id  # noqa: E402


class StructuredApiTests(unittest.TestCase):
    def test_request_accepts_camel_case_session_id(self):
        request = AssistantRequest(
            message="  find apples  ",
            sessionId="31f532db-9403-4d11-9667-b4d18c2043dc",
        )
        self.assertEqual(request.message, "find apples")
        self.assertEqual(request.session_id, "31f532db-9403-4d11-9667-b4d18c2043dc")

    def test_structured_cart_uses_camel_case_fields(self):
        payload = StructuredAssistantPayload(
            responseType=ResponseType.CART,
            message="Your cart has one item.",
            cart={
                "items": [
                    {
                        "productId": "p-1",
                        "name": "Apple",
                        "quantity": 2,
                        "unitPrice": 1.25,
                        "lineTotal": 2.50,
                    }
                ],
                "total": 2.50,
            },
        )
        body = payload.model_dump(by_alias=True)
        self.assertEqual(body["cart"]["items"][0]["productId"], "p-1")
        self.assertEqual(body["cart"]["items"][0]["lineTotal"], 2.50)

    def test_invalid_session_id_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "sessionId must be a UUID"):
            normalize_session_id("not-a-uuid")

    def test_llamaindex_retrieves_policy_document(self):
        _retriever.cache_clear()
        citations = retrieve_policy_context("How long do I have to return an item?")
        self.assertTrue(citations)
        self.assertEqual(citations[0].source, "returns-and-shipping.md")

    def test_policy_retrieval_does_not_access_nltk_data(self):
        _retriever.cache_clear()
        with patch("nltk.data.find", side_effect=AssertionError("NLTK data accessed")):
            citations = retrieve_policy_context("What is your privacy policy?")
        self.assertTrue(citations)
        self.assertEqual(citations[0].source, "privacy.md")

    def test_commerce_query_does_not_attach_policy_citations(self):
        self.assertEqual(retrieve_policy_context("Find apples under five dollars"), [])

    def test_formatter_failure_returns_safe_fallback(self):
        with patch.object(
            service, "_structured_formatter", side_effect=RuntimeError("unavailable")
        ):
            payload = service.format_answer(
                "Can I check out?", "Please confirm checkout.", []
            )
        self.assertEqual(payload.message, "Please confirm checkout.")
        self.assertTrue(payload.requires_confirmation)

    def test_endpoint_adds_server_owned_session_and_citations(self):
        payload = StructuredAssistantPayload(
            responseType=ResponseType.PRODUCT_SEARCH,
            message="I found one product.",
            products=[{"productId": "p-1", "name": "Apple", "price": 1.25}],
        )
        with (
            patch.object(app, "normalize_session_id", return_value="session-1"),
            patch.object(app, "claim_session") as claim_session,
            patch.object(app.service, "answer", return_value=(payload, [])),
        ):
            response = app.assistant(
                AssistantRequest(message="find apples"), user_sub="customer-1"
            )

        claim_session.assert_called_once_with("session-1", "customer-1")
        body = response.model_dump(by_alias=True)
        self.assertEqual(body["sessionId"], "session-1")
        self.assertEqual(body["responseType"], "product_search")
        self.assertEqual(body["products"][0]["productId"], "p-1")


if __name__ == "__main__":
    unittest.main()
