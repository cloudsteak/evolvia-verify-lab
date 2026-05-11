import os

import boto3


def lambda_handler(event, context):
    try:
        api_key = (event.get("headers") or {}).get("x-api-key", "")
        ssm = boto3.client("ssm")
        param = ssm.get_parameter(
            Name=os.environ["API_KEY_SSM_PARAM"],
            WithDecryption=True,
        )
        expected = param["Parameter"]["Value"]
        return api_key == expected
    except Exception:
        return False
