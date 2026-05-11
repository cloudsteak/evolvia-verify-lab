import json
import os
from pathlib import Path

import boto3
from botocore.exceptions import ClientError


def _get_name_tag(tags: list[dict] | None) -> str | None:
    if not tags:
        return None
    for tag in tags:
        if tag.get("Key") == "Name":
            return tag.get("Value")
    return None


def _verify(account_id: str) -> dict:
    spec_path = Path(__file__).parent / "lab_spec.json"
    with open(spec_path, "r", encoding="utf-8") as f:
        spec = json.load(f)

    region = spec["region"]
    checks = spec["checks"]
    ec2 = boto3.client("ec2", region_name=region)
    sts = boto3.client("sts", region_name=region)

    current_account_id = sts.get_caller_identity()["Account"]
    if current_account_id != account_id:
        return {
            "success": False,
            "message": (
                f"Hibás AWS account azonosító: {current_account_id}. "
                f"Elvárt: {account_id}."
            ),
        }

    instance_spec = checks["instance"]
    reservations = ec2.describe_instances(
        Filters=[{"Name": "tag:Name", "Values": [f"{instance_spec['prefix']}*"]}]
    )["Reservations"]
    instances = [
        instance
        for reservation in reservations
        for instance in reservation["Instances"]
        if instance.get("State", {}).get("Name") not in {"terminated", "shutting-down"}
    ]

    if len(instances) < instance_spec["count"]:
        return {
            "success": False,
            "message": (
                f"Nem található elegendő EC2 instance, amely "
                f"'{instance_spec['prefix']}' prefixszel kezdődik. "
                f"Elvárt: {instance_spec['count']}, Talált: {len(instances)}"
            ),
        }

    for instance in instances:
        if instance["InstanceType"] != instance_spec["instance_type"]:
            return {
                "success": False,
                "message": (
                    f"EC2 instance típusa hibás: "
                    f"{instance['InstanceId']} - {instance['InstanceType']}"
                ),
            }

        if instance["ImageId"] != instance_spec["image_id"]:
            return {
                "success": False,
                "message": (
                    f"EC2 instance image-je hibás: "
                    f"{instance['InstanceId']} - {instance['ImageId']}. "
                    f"Elvárt: {instance_spec['image_id']}"
                ),
            }

    return {"success": True, "message": "Lab sikeresen ellenőrizve."}


def lambda_handler(event, context):
    try:
        account_id = os.environ["AWS_ACCOUNT_ID"]
        result = _verify(account_id)
    except ClientError as error:
        result = {"success": False, "message": f"AWS hiba történt: {error}"}
    except Exception as error:
        result = {"success": False, "message": str(error)}

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(result),
    }
