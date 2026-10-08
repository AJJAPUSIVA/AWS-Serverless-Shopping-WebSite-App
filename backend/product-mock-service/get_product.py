import json
import os

from aws_lambda_powertools import Logger, Tracer
from mysql_repository import NotFoundError, get_product

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
    """
    Return single product based on path parameter.
    """
    path_params = event["pathParameters"]
    product_id = path_params.get("product_id")
    logger.debug("Retriving product_id: %s", product_id)
    try:
        product = get_product(product_id)
    except NotFoundError:
        return {
            "statusCode": 404,
            "headers": HEADERS,
            "body": json.dumps({"message": "Product not found"}),
        }

    return {
        "statusCode": 200,
        "headers": HEADERS,
        "body": json.dumps({"product": product}),
    }
