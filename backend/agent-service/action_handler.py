import json
import os
from decimal import Decimal

import boto3
from mysql_repository import (
    EmptyCartError,
    InventoryError,
    NotFoundError,
    add_cart_item,
    cart_total,
    checkout_cart,
    get_inventory,
    list_products,
    order_history,
    sales_summary,
    set_cart_item_quantity,
    user_owner_key,
)


SESSION_TABLE_NAME = os.environ["SESSION_TABLE_NAME"]
session_table = boto3.resource("dynamodb").Table(SESSION_TABLE_NAME)


class ToolInputError(ValueError):
    """Raised when the agent supplies a parameter that should be corrected."""


def _parameters(event):
    return {item["name"]: item.get("value") for item in event.get("parameters", [])}


def _response(event, result, response_state=None):
    function_response = {"responseBody": {"TEXT": {"body": json.dumps(result)}}}
    if response_state:
        function_response["responseState"] = response_state
    return {
        "messageVersion": "1.0",
        "response": {
            "actionGroup": event["actionGroup"],
            "function": event["function"],
            "functionResponse": function_response,
        },
        "sessionAttributes": event.get("sessionAttributes", {}),
        "promptSessionAttributes": event.get("promptSessionAttributes", {}),
    }


def _user_sub(session_id):
    item = session_table.get_item(
        Key={"sessionId": session_id}, ConsistentRead=True
    ).get("Item")
    if not item or not item.get("userSub"):
        raise RuntimeError("The assistant session is no longer valid")
    return item["userSub"]


def _quantity(value, allow_zero=False):
    try:
        quantity = int(value)
    except (TypeError, ValueError) as error:
        raise ToolInputError("Quantity must be a whole number") from error
    minimum = 0 if allow_zero else 1
    if quantity < minimum or quantity > 99:
        raise ToolInputError(f"Quantity must be between {minimum} and 99")
    return quantity


def search_products(parameters, _user_sub_value):
    max_price = parameters.get("max_price")
    max_price_cents = None
    if max_price not in (None, ""):
        try:
            max_price_cents = int(Decimal(str(max_price)) * 100)
        except Exception as error:
            raise ToolInputError("max_price must be a number in dollars") from error
        if max_price_cents < 0:
            raise ToolInputError("max_price cannot be negative")
    products = list_products(
        query=(parameters.get("query") or "").strip() or None,
        category=(parameters.get("category") or "").strip() or None,
        max_price_cents=max_price_cents,
        limit=8,
    )
    result = [
        {
            "productId": product["productId"],
            "name": product["name"],
            "category": product["category"],
            "description": product["description"],
            "price": product["price"] / 100,
            "availableQuantity": product["availableQuantity"],
        }
        for product in products
    ]
    return {"products": result, "matchCount": len(result)}


def check_inventory(parameters, _user_sub_value):
    return get_inventory(parameters.get("product_id"))


def get_cart(_parameters, user_sub_value):
    return cart_total(user_owner_key(user_sub_value))


def add_to_cart(parameters, user_sub_value):
    quantity = _quantity(parameters.get("quantity"))
    product_id = parameters.get("product_id")
    result = add_cart_item(
        user_owner_key(user_sub_value),
        product_id,
        quantity,
        customer_sub=user_sub_value,
    )
    return {
        "message": f"Added {quantity} x {result['name']} to the cart",
        "cart": cart_total(user_owner_key(user_sub_value)),
    }


def update_cart_quantity(parameters, user_sub_value):
    quantity = _quantity(parameters.get("quantity"), allow_zero=True)
    product_id = parameters.get("product_id")
    result = set_cart_item_quantity(
        user_owner_key(user_sub_value),
        product_id,
        quantity,
        customer_sub=user_sub_value,
    )
    return {
        "message": f"Set {result['name']} quantity to {quantity}",
        "cart": cart_total(user_owner_key(user_sub_value)),
    }


def preview_checkout(_parameters, user_sub_value):
    summary = cart_total(user_owner_key(user_sub_value))
    summary["message"] = "Checkout preview only; no order was created"
    return summary


def confirm_checkout(_parameters, user_sub_value):
    order = checkout_cart(user_sub_value)
    return {"message": "Order placed and inventory updated", "order": order}


def get_order_history(parameters, user_sub_value):
    limit = parameters.get("limit") or 10
    try:
        return {"orders": order_history(user_sub_value, limit=int(limit))}
    except (TypeError, ValueError) as error:
        raise ToolInputError("limit must be a whole number") from error


def get_sales_summary(parameters, _user_sub_value):
    limit = parameters.get("limit") or 5
    try:
        return {"products": sales_summary(limit=int(limit))}
    except (TypeError, ValueError) as error:
        raise ToolInputError("limit must be a whole number") from error


FUNCTIONS = {
    "search_products": search_products,
    "check_inventory": check_inventory,
    "get_cart": get_cart,
    "add_to_cart": add_to_cart,
    "update_cart_quantity": update_cart_quantity,
    "preview_checkout": preview_checkout,
    "confirm_checkout": confirm_checkout,
    "get_order_history": get_order_history,
    "get_sales_summary": get_sales_summary,
}


def lambda_handler(event, context):
    del context
    function_name = event.get("function")
    handler = FUNCTIONS.get(function_name)
    if not handler:
        return _response(
            event,
            {"error": f"Unsupported shopping function: {function_name}"},
            response_state="FAILURE",
        )
    try:
        result = handler(_parameters(event), _user_sub(event["sessionId"]))
        return _response(event, result)
    except (ToolInputError, NotFoundError, InventoryError, EmptyCartError, ValueError) as error:
        return _response(event, {"error": str(error)}, response_state="REPROMPT")
    except Exception:
        return _response(
            event,
            {"error": "The shopping service could not complete that action"},
            response_state="FAILURE",
        )
