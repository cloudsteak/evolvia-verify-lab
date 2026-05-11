import json
import logging
import os

import boto3
from botocore.exceptions import ClientError

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO").upper())

REQUIRED_FIELDS = ["user", "email", "cloud", "lab"]


def _validate(body: dict) -> str | None:
    for field in REQUIRED_FIELDS:
        if not body.get(field, "").strip():
            return f"Hiányzó vagy üres mező: '{field}'."
    return None


def lambda_handler(event, context):
    request_context = event.get("requestContext", {})
    source_ip = (
        request_context.get("http", {}).get("sourceIp")
        or request_context.get("identity", {}).get("sourceIp")
        or "ismeretlen"
    )

    logger.info(
        "Kérés érkezett: request_id=%s source_ip=%s route=%s",
        context.aws_request_id,
        source_ip,
        request_context.get("http", {}).get("path", "ismeretlen"),
    )

    body = json.loads(event.get("body") or "{}")

    error = _validate(body)
    if error:
        logger.warning("Validációs hiba: %s request_id=%s", error, context.aws_request_id)
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"success": False, "message": error}),
        }

    lab = body["lab"].strip().lower()
    function_name = f"{os.environ['FUNCTION_PREFIX']}-{lab}"
    logger.info(
        "Dispatching: user=%s lab=%s function=%s",
        body["user"],
        lab,
        function_name,
    )

    try:
        lambda_client = boto3.client("lambda")
        response = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType="RequestResponse",
            Payload=json.dumps(event),
        )
    except ClientError as error:
        if error.response["Error"]["Code"] == "ResourceNotFoundException":
            msg = f"Ismeretlen lab: '{lab}'."
            logger.warning("Lab nem található: %s request_id=%s", msg, context.aws_request_id)
            return {
                "statusCode": 404,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"success": False, "message": msg}),
            }
        logger.exception("Lambda invoke hiba: %s", error)
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"success": False, "message": "Belső hiba történt."}),
        }

    if response.get("FunctionError"):
        logger.error("Lambda hiba: function=%s error=%s", function_name, response["FunctionError"])
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"success": False, "message": "Belső hiba történt."}),
        }

    result = json.loads(response["Payload"].read())
    logger.info(
        "Kérés lezárva: request_id=%s user=%s lab=%s statusCode=%s",
        context.aws_request_id,
        body["user"],
        lab,
        result.get("statusCode"),
    )
    return result
