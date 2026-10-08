import json

from aws_lambda_powertools import Logger, Metrics, Tracer
from mysql_repository import EmptyCartError, InventoryError, checkout_cart
from shared import get_headers

logger = Logger()
tracer = Tracer()
metrics = Metrics()


@metrics.log_metrics(capture_cold_start_metric=True)
@logger.inject_lambda_context(log_event=False)
@tracer.capture_lambda_handler
def lambda_handler(event, context):
    del context
    user_sub = event["requestContext"]["authorizer"]["claims"]["sub"]
    try:
        order = checkout_cart(user_sub)
    except EmptyCartError as error:
        return {"statusCode": 400, "headers": get_headers(), "body": json.dumps({"message": str(error)})}
    except InventoryError as error:
        return {"statusCode": 409, "headers": get_headers(), "body": json.dumps({"message": str(error)})}

    metrics.add_metric(name="CartCheckedOut", unit="Count", value=1)
    return {
        "statusCode": 201,
        "headers": get_headers(),
        "body": json.dumps({"order": order, "message": "Order placed"}),
    }
