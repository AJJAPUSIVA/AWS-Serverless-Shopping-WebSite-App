"""Apply the commerce schema to a password-authenticated MySQL instance.

Used by CI and local development. AWS deployment uses schema_loader.py with
IAM authentication through RDS Proxy.
"""

import os
import pathlib

import pymysql


def main():
    sql = (pathlib.Path(__file__).parent / "schema.sql").read_text(encoding="utf-8")
    statements = [statement.strip() for statement in sql.split(";") if statement.strip()]
    connection = pymysql.connect(
        host=os.environ.get("DB_HOST", "127.0.0.1"),
        port=int(os.environ.get("DB_PORT", "3306")),
        user=os.environ["DB_USER"],
        password=os.environ["MYSQL_PASSWORD"],
        database=os.environ["DB_NAME"],
        charset="utf8mb4",
        autocommit=False,
    )
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


if __name__ == "__main__":
    main()
