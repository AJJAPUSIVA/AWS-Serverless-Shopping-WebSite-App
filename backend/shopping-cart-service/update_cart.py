import json

from aws_lambda_powertools import Logger, Metrics, Tracer
from mysql_repository import InventoryError, NotFoundError, set_cart_item_quantity, user_owner_key
from shared import get_headers

logger = Logger()
tracer = Tracer()
metrics = Metrics()


def _response(status_code, message):
    return {"statusCode": status_code, "headers": get_headers(), "body": json.dumps({"message": message})}


@metrics.log_metrics(capture_cold_start_metric=True)
@logger.inject_lambda_context(log_event=False)
@tracer.capture_lambda_handler
def lambda_handler(event, context):
    del context
    try:
        payload = json.loads(event.get("body") or "{}")
        quantity = int(payload["quantity"])
        product_id = event["pathParameters"]["product_id"]
        user_sub = event["requestContext"]["authorizer"]["claims"]["sub"]
        result = set_cart_item_quantity(
            user_owner_key(user_sub), product_id, quantity, customer_sub=user_sub
        )
    except (KeyError, TypeError, ValueError) as error:
        return _response(400, str(error))
    except NotFoundError as error:
        return _response(404, str(error))
    except InventoryError as error:
        return _response(409, str(error))

    metrics.add_metric(name="CartUpdated", unit="Count", value=1)
    return {
        "statusCode": 200,
        "headers": get_headers(),
        "body": json.dumps({**result, "message": "Cart updated"}),
    }
