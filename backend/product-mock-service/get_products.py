import json
import os

from aws_lambda_powertools import Logger, Tracer
from mysql_repository import list_products

logger = Logger()
tracer = Tracer()

HEADERS = {
    "Access-Control-Allow-Origin": os.environ.get("ALLOWED_ORIGIN"),
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "OPTIONS,POST,GET",
}


@logger.inject_lambda_context(log_event=True)
@tracer.capture_lambda_handler
def lambda_handler(event, context):
    """Return products from the authoritative MySQL catalog."""
    logger.debug("Fetching product list")
    parameters = event.get("queryStringParameters") or {}
    max_price = parameters.get("maxPrice")
    try:
        max_price_cents = int(max_price) if max_price is not None else None
    except ValueError:
        return {
            "statusCode": 400,
            "headers": HEADERS,
            "body": json.dumps({"message": "maxPrice must be an integer number of cents"}),
        }
    products = list_products(
        query=parameters.get("query"),
        category=parameters.get("category"),
        max_price_cents=max_price_cents,
    )

    return {
        "statusCode": 200,
        "headers": HEADERS,
        "body": json.dumps({"products": products}),
    }
