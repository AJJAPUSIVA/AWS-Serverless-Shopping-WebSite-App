import json
import os
import pathlib
import time
import urllib.request

import boto3
import pymysql


def _send(event, context, status, reason=None):
    body = json.dumps(
        {
            "Status": status,
            "Reason": reason or f"See CloudWatch Logs: {context.log_stream_name}",
            "PhysicalResourceId": event.get("PhysicalResourceId", "mysql-commerce-schema"),
            "StackId": event["StackId"],
            "RequestId": event["RequestId"],
            "LogicalResourceId": event["LogicalResourceId"],
            "NoEcho": False,
            "Data": {},
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        event["ResponseURL"],
        data=body,
        method="PUT",
        headers={"content-type": "", "content-length": str(len(body))},
    )
    with urllib.request.urlopen(request, timeout=10):
        pass


def _connect():
    host = os.environ["DB_HOST"]
    port = int(os.environ.get("DB_PORT", "3306"))
    user = os.environ["DB_USER"]
    token = boto3.client("rds").generate_db_auth_token(
        DBHostname=host,
        Port=port,
        DBUsername=user,
        Region=os.environ["AWS_REGION"],
    )
    for attempt in range(12):
        try:
            return pymysql.connect(
                host=host,
                port=port,
                user=user,
                password=token,
                database=os.environ["DB_NAME"],
                charset="utf8mb4",
                autocommit=False,
                connect_timeout=10,
                ssl={"ca": "/etc/pki/tls/certs/ca-bundle.crt"},
                ssl_verify_cert=True,
                ssl_verify_identity=True,
            )
        except pymysql.MySQLError:
            if attempt == 11:
                raise
            time.sleep(10)


def lambda_handler(event, context):
    if event["RequestType"] == "Delete":
        _send(event, context, "SUCCESS")
        return

    try:
        sql = (pathlib.Path(__file__).parent / "schema.sql").read_text(encoding="utf-8")
        statements = [statement.strip() for statement in sql.split(";") if statement.strip()]
        connection = _connect()
        try:
            with connection.cursor() as cursor:
                for statement in statements:
                    cursor.execute(statement)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
    except Exception as error:
        _send(event, context, "FAILED", f"Schema migration failed: {type(error).__name__}")
        raise

    _send(event, context, "SUCCESS")
