import json
import os
import time
from decimal import Decimal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import boto3
from boto3.dynamodb.conditions import Key


PRODUCT_SERVICE_URL = os.environ["PRODUCT_SERVICE_URL"].rstrip("/")
CART_TABLE_NAME = os.environ["CART_TABLE_NAME"]
SESSION_TABLE_NAME = os.environ["SESSION_TABLE_NAME"]

dynamodb = boto3.resource("dynamodb")
cart_table = dynamodb.Table(CART_TABLE_NAME)
session_table = dynamodb.Table(SESSION_TABLE_NAME)


class ToolInputError(ValueError):
    """Raised when the agent supplies a parameter that should be corrected."""


def _json_default(value):
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    raise TypeError(f"Cannot serialize {type(value).__name__}")


def _parameters(event):
    return {item["name"]: item.get("value") for item in event.get("parameters", [])}


def _response(event, result, response_state=None):
    function_response = {
        "responseBody": {
            "TEXT": {"body": json.dumps(result, default=_json_default)}
        }
    }
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


def _fetch_json(path):
    request = Request(
        f"{PRODUCT_SERVICE_URL}{path}",
        headers={"Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=4) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        if error.code == 404:
            raise ToolInputError("Product not found") from error
        raise RuntimeError("Product service request failed") from error
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        raise RuntimeError("Product service is unavailable") from error


def _identity_key(session_id):
    item = session_table.get_item(
        Key={"sessionId": session_id}, ConsistentRead=True
    ).get("Item")
    if not item or not item.get("userSub"):
        raise RuntimeError("The assistant session is no longer valid")
    return f"user#{item['userSub']}"


def _cart_items(identity_key):
    items = []
    query = {
        "KeyConditionExpression": Key("pk").eq(identity_key)
        & Key("sk").begins_with("product#"),
        "ConsistentRead": True,
    }
    while True:
        response = cart_table.query(**query)
        items.extend(item for item in response.get("Items", []) if item.get("quantity", 0) > 0)
        if "LastEvaluatedKey" not in response:
            break
        query["ExclusiveStartKey"] = response["LastEvaluatedKey"]
    return items


def _cart_summary(identity_key):
    items = _cart_items(identity_key)
    products = []
    total_cents = Decimal(0)
    for item in items:
        product = item.get("productDetail", {})
        quantity = int(item.get("quantity", 0))
        price_cents = Decimal(str(product.get("price", 0)))
        total_cents += price_cents * quantity
        products.append(
            {
                "productId": item["sk"].replace("product#", "", 1),
                "name": product.get("name", "Unknown product"),
                "quantity": quantity,
                "unitPrice": float(price_cents / 100),
            }
        )
    return {"products": products, "total": float(total_cents / 100)}


def _get_product(product_id):
    if not product_id:
        raise ToolInputError("A product_id is required")
    payload = _fetch_json(f"/product/{product_id}")
    product = payload.get("product")
    if not product:
        raise ToolInputError("Product not found")
    return product


def _positive_quantity(value):
    try:
        quantity = int(value)
    except (TypeError, ValueError) as error:
        raise ToolInputError("Quantity must be a whole number") from error
    if quantity < 1 or quantity > 99:
        raise ToolInputError("Quantity must be between 1 and 99")
    return quantity


def search_products(parameters, _identity_key_value):
    query = (parameters.get("query") or "").strip().lower()
    category = (parameters.get("category") or "").strip().lower()
    max_price = parameters.get("max_price")
    max_price_cents = None
    if max_price not in (None, ""):
        try:
            max_price_cents = Decimal(str(max_price)) * 100
        except Exception as error:
            raise ToolInputError("max_price must be a number in dollars") from error
        if max_price_cents < 0:
            raise ToolInputError("max_price cannot be negative")

    products = _fetch_json("/product").get("products", [])
    matches = []
    for product in products:
        searchable = " ".join(
            [
                product.get("name", ""),
                product.get("description", ""),
                " ".join(product.get("tags", [])),
            ]
        ).lower()
        if query and query not in searchable:
            continue
        if category and product.get("category", "").lower() != category:
            continue
        if max_price_cents is not None and Decimal(str(product.get("price", 0))) > max_price_cents:
            continue
        matches.append(
            {
                "productId": product["productId"],
                "name": product["name"],
                "category": product.get("category"),
                "description": product.get("description"),
                "price": float(Decimal(str(product.get("price", 0))) / 100),
            }
        )
    matches.sort(key=lambda product: (product["price"], product["name"]))
    return {"products": matches[:8], "matchCount": len(matches)}


def get_cart(_parameters, identity_key_value):
    return _cart_summary(identity_key_value)


def add_to_cart(parameters, identity_key_value):
    product_id = parameters.get("product_id")
    quantity = _positive_quantity(parameters.get("quantity"))
    product = _get_product(product_id)
    expiration_time = int(time.time()) + (7 * 24 * 60 * 60)
    cart_table.update_item(
        Key={"pk": identity_key_value, "sk": f"product#{product_id}"},
        ExpressionAttributeNames={
            "#quantity": "quantity",
            "#expiration": "expirationTime",
            "#product": "productDetail",
        },
        ExpressionAttributeValues={
            ":quantity": quantity,
            ":expiration": expiration_time,
            ":product": product,
        },
        UpdateExpression=(
            "ADD #quantity :quantity "
            "SET #expiration = :expiration, #product = :product"
        ),
    )
    return {
        "message": f"Added {quantity} x {product['name']} to the cart",
        "cart": _cart_summary(identity_key_value),
    }


def update_cart_quantity(parameters, identity_key_value):
    product_id = parameters.get("product_id")
    try:
        quantity = int(parameters.get("quantity"))
    except (TypeError, ValueError) as error:
        raise ToolInputError("Quantity must be a whole number") from error
    if quantity < 0 or quantity > 99:
        raise ToolInputError("Quantity must be between 0 and 99")

    product = _get_product(product_id)
    cart_table.put_item(
        Item={
            "pk": identity_key_value,
            "sk": f"product#{product_id}",
            "quantity": quantity,
            "expirationTime": int(time.time()) + (7 * 24 * 60 * 60),
            "productDetail": product,
        }
    )
    return {
        "message": f"Set {product['name']} quantity to {quantity}",
        "cart": _cart_summary(identity_key_value),
    }


def preview_checkout(_parameters, identity_key_value):
    summary = _cart_summary(identity_key_value)
    summary["message"] = "Checkout preview only; no items were removed"
    return summary


def confirm_checkout(_parameters, identity_key_value):
    items = _cart_items(identity_key_value)
    with cart_table.batch_writer() as batch:
        for item in items:
            batch.delete_item(Key={"pk": item["pk"], "sk": item["sk"]})
    return {"message": "Checkout completed and the cart was cleared", "itemCount": len(items)}


FUNCTIONS = {
    "search_products": search_products,
    "get_cart": get_cart,
    "add_to_cart": add_to_cart,
    "update_cart_quantity": update_cart_quantity,
    "preview_checkout": preview_checkout,
    "confirm_checkout": confirm_checkout,
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
        identity_key_value = _identity_key(event["sessionId"])
        result = handler(_parameters(event), identity_key_value)
        return _response(event, result)
    except ToolInputError as error:
        return _response(event, {"error": str(error)}, response_state="REPROMPT")
    except Exception:
        return _response(
            event,
            {"error": "The shopping service could not complete that action"},
            response_state="FAILURE",
        )
