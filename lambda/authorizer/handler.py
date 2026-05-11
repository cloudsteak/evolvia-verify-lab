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
    if event.get("warmup"):
        logger.info("Warmup hívás — kihagyás")
        return {"isAuthorized": False}

    try:
        api_key = (event.get("headers") or {}).get("x-api-key", "")
        ssm = boto3.client("ssm")
        param = ssm.get_parameter(
            Name=os.environ["API_KEY_SSM_PARAM"],
            WithDecryption=True,
        )
        expected = param["Parameter"]["Value"]
        authorized = api_key == expected
        logger.info("Authorizer eredmény: authorized=%s", authorized)
        return {"isAuthorized": authorized}
    except Exception as error:
        logger.exception("Authorizer hiba: %s", error)
        return {"isAuthorized": False}
