import json
import logging
import os
import urllib.request
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request

import boto3
from botocore.exceptions import ClientError

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO").upper())


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def http_error_301(self, req, fp, code, msg, headers):
        raise HTTPError(req.full_url, code, msg, headers, fp)

    http_error_302 = http_error_303 = http_error_307 = http_error_308 = http_error_301


_http_opener = urllib.request.build_opener(_NoRedirectHandler)


def _http_status(url: str, timeout: int = 10) -> int:
    request = Request(url, method="GET")
    try:
        with _http_opener.open(request, timeout=timeout) as response:
            return response.status
    except HTTPError as error:
        return error.code


def _verify(account_id: str, user: str) -> dict:
    spec_path = Path(__file__).parent / "lab_spec.json"
    with open(spec_path, "r", encoding="utf-8") as f:
        spec = json.load(f)

    region = spec["region"]
    checks = spec["checks"]
    instance_spec = checks["instance"]
    website_spec = checks["website"]

    logger.debug("Spec betöltve: region=%s checks=%s", region, json.dumps(checks))

    ec2 = boto3.client("ec2", region_name=region)
    sts = boto3.client("sts", region_name=region)

    logger.debug("API hívás: sts:GetCallerIdentity")
    current_account_id = sts.get_caller_identity()["Account"]
    logger.debug("sts:GetCallerIdentity válasz: account_id=%s", current_account_id)

    if current_account_id != account_id:
        msg = f"Hibás AWS account azonosító: {current_account_id}. Elvárt: {account_id}."
        logger.warning("Ellenőrzés sikertelen: %s", msg)
        return {"success": False, "message": msg}

    owner_filters = [{"Name": "tag:owner", "Values": [user]}]
    logger.debug("API hívás: ec2:DescribeInstances (owner szűrő) filters=%s", json.dumps(owner_filters))
    owner_reservations = ec2.describe_instances(Filters=owner_filters)["Reservations"]
    owner_instances = [
        instance
        for reservation in owner_reservations
        for instance in reservation["Instances"]
        if instance.get("State", {}).get("Name") not in {"terminated", "shutting-down"}
    ]
    logger.debug("Owner alapján talált instance-ek: %d (user=%s)", len(owner_instances), user)

    if not owner_instances:
        msg = f"Nincs EC2 instance a(z) '{user}' felhasználóhoz."
        logger.warning("Ellenőrzés sikertelen: %s", msg)
        return {"success": False, "message": msg}

    filters = [
        {"Name": "tag:owner", "Values": [user]},
        {"Name": "tag:Name", "Values": [f"{instance_spec['prefix']}*"]},
        {"Name": "instance-state-name", "Values": ["running"]},
    ]
    logger.debug("API hívás: ec2:DescribeInstances (lab szűrő) filters=%s", json.dumps(filters))
    reservations = ec2.describe_instances(Filters=filters)["Reservations"]
    instances = [
        instance
        for reservation in reservations
        for instance in reservation["Instances"]
    ]
    logger.debug("Lab feltételnek megfelelő instance-ek: %d", len(instances))

    if len(instances) < instance_spec["count"]:
        msg = (
            f"Nem található elegendő futó EC2 instance, amely "
            f"'{instance_spec['prefix']}' prefixszel kezdődik. "
            f"Elvárt: {instance_spec['count']}, Talált: {len(instances)}"
        )
        logger.warning("Ellenőrzés sikertelen: %s", msg)
        return {"success": False, "message": msg}

    expected_status_codes = set(website_spec["expected_status_codes"])
    port = website_spec["port"]

    for instance in instances:
        logger.debug(
            "Instance ellenőrzése: id=%s type=%s state=%s",
            instance["InstanceId"],
            instance["InstanceType"],
            instance.get("State", {}).get("Name"),
        )

        if instance["InstanceType"] != instance_spec["instance_type"]:
            msg = f"EC2 instance típusa hibás: {instance['InstanceId']} - {instance['InstanceType']}"
            logger.warning("Ellenőrzés sikertelen: %s", msg)
            return {"success": False, "message": msg}

        host = instance.get("PublicDnsName") or instance.get("PublicIpAddress")
        if not host:
            msg = f"Az EC2 instance nem rendelkezik nyilvános címmel: {instance['InstanceId']}"
            logger.warning("Ellenőrzés sikertelen: %s", msg)
            return {"success": False, "message": msg}

        url = f"http://{host}:{port}"
        logger.debug("HTTP ellenőrzés: url=%s instance=%s", url, instance["InstanceId"])
        try:
            status_code = _http_status(url)
        except URLError as error:
            msg = (
                f"A weboldal nem érhető el a {port}-as porton. "
                f"Instance: {instance['InstanceId']}. Hiba: {error}"
            )
            logger.warning("Ellenőrzés sikertelen: %s", msg)
            return {"success": False, "message": msg}

        if status_code not in expected_status_codes:
            msg = (
                f"A weboldal hibás HTTP státuszkódot ad vissza: "
                f"{status_code}. Instance: {instance['InstanceId']}"
            )
            logger.warning("Ellenőrzés sikertelen: %s", msg)
            return {"success": False, "message": msg}

    msg = "Lab sikeresen ellenőrizve."
    logger.info("Ellenőrzés sikeres: %s", msg)
    return {"success": True, "message": msg}


def lambda_handler(event, context):
    if event.get("warmup"):
        logger.info("Warmup hívás — kihagyás")
        return {}

    request_context = event.get("requestContext", {})
    source_ip = (
        request_context.get("http", {}).get("sourceIp")
        or request_context.get("identity", {}).get("sourceIp")
        or "ismeretlen"
    )
    account_id = os.environ["AWS_ACCOUNT_ID"]
    body = json.loads(event.get("body") or "{}")
    user = body.get("user", "").strip()

    logger.info(
        "Kérés érkezett: request_id=%s source_ip=%s account_id=%s user=%s",
        context.aws_request_id,
        source_ip,
        account_id,
        user,
    )

    try:
        result = _verify(account_id, user)
    except ClientError as error:
        logger.exception("AWS API hiba")
        result = {"success": False, "message": f"AWS hiba történt: {error}"}
    except Exception as error:
        logger.exception("Váratlan hiba")
        result = {"success": False, "message": str(error)}

    logger.info(
        "Kérés lezárva: request_id=%s user=%s success=%s message=%s",
        context.aws_request_id,
        user,
        result["success"],
        result["message"],
    )

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(result),
    }
