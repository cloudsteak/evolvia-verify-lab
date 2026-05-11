import json
import os
from pathlib import Path

import boto3
from botocore.exceptions import ClientError


def _verify(account_id: str) -> dict:
    spec_path = Path(__file__).parent / "lab_spec.json"
    with open(spec_path, "r", encoding="utf-8") as f:
        spec = json.load(f)

    checks = spec["checks"]
    region = os.environ.get("AWS_REGION", "eu-north-1")
    rds = boto3.client("rds", region_name=region)
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

    db_spec = checks["db_instance"]
    db_instances = rds.describe_db_instances()["DBInstances"]
    matching_instances = [
        instance
        for instance in db_instances
        if instance["DBInstanceIdentifier"].startswith(db_spec["prefix"])
    ]

    if len(matching_instances) < db_spec["count"]:
        return {
            "success": False,
            "message": (
                f"Nem található elegendő RDS példány, amely "
                f"'{db_spec['prefix']}' prefixszel kezdődik. "
                f"Elvárt: {db_spec['count']}, Talált: {len(matching_instances)}"
            ),
        }

    for instance in matching_instances:
        if instance["Engine"] != db_spec["engine"]:
            return {
                "success": False,
                "message": (
                    f"RDS engine hibás: {instance['DBInstanceIdentifier']} - "
                    f"{instance['Engine']}"
                ),
            }

        if instance["DBInstanceClass"] != db_spec["instance_class"]:
            return {
                "success": False,
                "message": (
                    f"RDS példányosztály hibás: "
                    f"{instance['DBInstanceIdentifier']} - "
                    f"{instance['DBInstanceClass']}"
                ),
            }

        if instance["DBInstanceStatus"] != db_spec["expected_status"]:
            return {
                "success": False,
                "message": (
                    f"RDS állapot hibás: {instance['DBInstanceIdentifier']} - "
                    f"{instance['DBInstanceStatus']}. "
                    f"Elvárt: {db_spec['expected_status']}"
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
