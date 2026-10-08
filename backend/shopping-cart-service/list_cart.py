import json

from aws_lambda_powertools import Logger, Tracer
from mysql_repository import list_cart, user_owner_key
from shared import get_headers

logger = Logger()
tracer = Tracer()


@logger.inject_lambda_context(log_event=False)
@tracer.capture_lambda_handler
def lambda_handler(event, context):
    del context
    user_sub = event["requestContext"]["authorizer"]["claims"]["sub"]
    products = list_cart(user_owner_key(user_sub))
    return {
        "statusCode": 200,
        "headers": get_headers(),
        "body": json.dumps({"products": products}),
    }
