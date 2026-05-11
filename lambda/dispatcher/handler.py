import json
import logging
import os

import boto3

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO").upper())


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
    lab = body.get("lab", "").strip().lower()

    if not lab:
        logger.warning("Hiányzó 'lab' paraméter: request_id=%s", context.aws_request_id)
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"success": False, "message": "Hiányzó 'lab' paraméter."}),
        }

    function_name = f"{os.environ['FUNCTION_PREFIX']}-{lab}"
    logger.info("Dispatching: lab=%s function=%s", lab, function_name)

    lambda_client = boto3.client("lambda")
    response = lambda_client.invoke(
        FunctionName=function_name,
        InvocationType="RequestResponse",
        Payload=json.dumps(event),
    )

    if response.get("FunctionError"):
        logger.error("Lambda hiba: function=%s error=%s", function_name, response["FunctionError"])
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"success": False, "message": f"Ismeretlen lab: '{lab}'"}),
        }

    result = json.loads(response["Payload"].read())
    logger.info(
        "Kérés lezárva: request_id=%s lab=%s statusCode=%s",
        context.aws_request_id,
        lab,
        result.get("statusCode"),
    )
    return result
