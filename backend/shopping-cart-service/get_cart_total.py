import json

from aws_lambda_powertools import Logger, Tracer
from mysql_repository import cart_quantity_for_product
from shared import get_headers

logger = Logger()
tracer = Tracer()


@logger.inject_lambda_context(log_event=False)
@tracer.capture_lambda_handler
def lambda_handler(event, context):
    del context
    product_id = event["pathParameters"]["product_id"]
    return {
        "statusCode": 200,
        "headers": get_headers(),
        "body": json.dumps(
            {"product": product_id, "quantity": cart_quantity_for_product(product_id)}
        ),
    }
