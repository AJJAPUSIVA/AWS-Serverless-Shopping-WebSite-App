import json
import os
import time
import uuid

import boto3


ALLOWED_ORIGIN = os.environ["ALLOWED_ORIGIN"]
AGENT_ID = os.environ["AGENT_ID"]
AGENT_ALIAS_ID = os.environ["AGENT_ALIAS_ID"]
SESSION_TABLE_NAME = os.environ["SESSION_TABLE_NAME"]

bedrock_agent_runtime = boto3.client("bedrock-agent-runtime")
dynamodb = boto3.resource("dynamodb")
session_table = dynamodb.Table(SESSION_TABLE_NAME)


def _headers():
    return {
        "Access-Control-Allow-Origin": ALLOWED_ORIGIN,
        "Access-Control-Allow-Headers": "Content-Type,Authorization",
        "Access-Control-Allow-Methods": "OPTIONS,POST",
        "Access-Control-Allow-Credentials": True,
        "Content-Type": "application/json",
    }


def _response(status_code, body):
    return {"statusCode": status_code, "headers": _headers(), "body": json.dumps(body)}


def _session_id(value):
    if not value:
        return str(uuid.uuid4())
    try:
        parsed = uuid.UUID(value)
    except (ValueError, TypeError, AttributeError) as error:
        raise ValueError("sessionId must be a UUID") from error
    return str(parsed)


def _user_sub(event):
    return (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("claims", {})
        .get("sub")
    )


def _claim_session(session_id, user_sub):
    existing = session_table.get_item(
        Key={"sessionId": session_id}, ConsistentRead=True
    ).get("Item")
    if existing and existing.get("userSub") != user_sub:
        raise PermissionError("This assistant session belongs to another user")

    session_table.put_item(
        Item={
            "sessionId": session_id,
            "userSub": user_sub,
            "expirationTime": int(time.time()) + (24 * 60 * 60),
        }
    )


def _invoke_agent(message, session_id):
    response = bedrock_agent_runtime.invoke_agent(
        agentId=AGENT_ID,
        agentAliasId=AGENT_ALIAS_ID,
        sessionId=session_id,
        inputText=message,
        enableTrace=False,
    )
    chunks = []
    for event in response.get("completion", []):
        chunk = event.get("chunk")
        if chunk and chunk.get("bytes"):
            chunks.append(chunk["bytes"].decode("utf-8"))
    return "".join(chunks).strip()


def lambda_handler(event, context):
    del context
    user_sub = _user_sub(event)
    if not user_sub:
        return _response(401, {"message": "Sign in to use the shopping assistant"})

    try:
        payload = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return _response(400, {"message": "Request body must be valid JSON"})

    message = str(payload.get("message") or "").strip()
    if not message or len(message) > 2000:
        return _response(400, {"message": "Message must contain between 1 and 2000 characters"})

    try:
        session_id = _session_id(payload.get("sessionId"))
        _claim_session(session_id, user_sub)
        answer = _invoke_agent(message, session_id)
    except ValueError as error:
        return _response(400, {"message": str(error)})
    except PermissionError as error:
        return _response(403, {"message": str(error)})
    except Exception:
        return _response(502, {"message": "The shopping assistant is temporarily unavailable"})

    return _response(
        200,
        {
            "message": answer or "I could not produce a response. Please try again.",
            "sessionId": session_id,
        },
    )
