import json
import logging
import os
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO").upper())


def _verify(account_id: str, user: str) -> dict:
    spec_path = Path(__file__).parent / "lab_spec.json"
    with open(spec_path, "r", encoding="utf-8") as f:
        spec = json.load(f)

    region = spec["region"]
    checks = spec["checks"]
    instance_spec = checks["instance"]

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

    # 1. lépés: van-e egyáltalán EC2 a userhez?
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

    # 2. lépés: teljesülnek-e a lab kritériumok?
    filters = [
        {"Name": "tag:owner", "Values": [user]},
        {"Name": "tag:Name", "Values": [f"{instance_spec['prefix']}*"]},
    ]
    logger.debug("API hívás: ec2:DescribeInstances (lab szűrő) filters=%s", json.dumps(filters))
    reservations = ec2.describe_instances(Filters=filters)["Reservations"]
    instances = [
        instance
        for reservation in reservations
        for instance in reservation["Instances"]
        if instance.get("State", {}).get("Name") not in {"terminated", "shutting-down"}
    ]
    logger.debug("Lab feltételnek megfelelő instance-ek: %d", len(instances))

    if len(instances) < instance_spec["count"]:
        msg = (
            f"Nem található elegendő EC2 instance, amely "
            f"'{instance_spec['prefix']}' prefixszel kezdődik. "
            f"Elvárt: {instance_spec['count']}, Talált: {len(instances)}"
        )
        logger.warning("Ellenőrzés sikertelen: %s", msg)
        return {"success": False, "message": msg}

    for instance in instances:
        logger.debug(
            "Instance ellenőrzése: id=%s type=%s image=%s state=%s",
            instance["InstanceId"],
            instance["InstanceType"],
            instance["ImageId"],
            instance.get("State", {}).get("Name"),
        )

        if instance["InstanceType"] != instance_spec["instance_type"]:
            msg = f"EC2 instance típusa hibás: {instance['InstanceId']} - {instance['InstanceType']}"
            logger.warning("Ellenőrzés sikertelen: %s", msg)
            return {"success": False, "message": msg}

        if instance["ImageId"] != instance_spec["image_id"]:
            msg = (
                f"EC2 instance image-je hibás: "
                f"{instance['InstanceId']} - {instance['ImageId']}. "
                f"Elvárt: {instance_spec['image_id']}"
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
        logger.exception("AWS API hiba: %s", error)
        result = {"success": False, "message": f"AWS hiba történt: {error}"}
    except Exception as error:
        logger.exception("Váratlan hiba: %s", error)
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
