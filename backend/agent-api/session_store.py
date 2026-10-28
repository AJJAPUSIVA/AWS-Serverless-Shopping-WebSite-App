import os
import time
import uuid
from functools import lru_cache

import boto3


@lru_cache(maxsize=1)
def _session_table():
    return boto3.resource("dynamodb").Table(os.environ["SESSION_TABLE_NAME"])


def normalize_session_id(value: str | None) -> str:
    if not value:
        return str(uuid.uuid4())
    try:
        return str(uuid.UUID(value))
    except (ValueError, TypeError, AttributeError) as error:
        raise ValueError("sessionId must be a UUID") from error


def claim_session(session_id: str, user_sub: str) -> None:
    table = _session_table()
    existing = table.get_item(
        Key={"sessionId": session_id}, ConsistentRead=True
    ).get("Item")
    if existing and existing.get("userSub") != user_sub:
        raise PermissionError("This assistant session belongs to another user")

    table.put_item(
        Item={
            "sessionId": session_id,
            "userSub": user_sub,
            "expirationTime": int(time.time()) + (24 * 60 * 60),
        }
    )
