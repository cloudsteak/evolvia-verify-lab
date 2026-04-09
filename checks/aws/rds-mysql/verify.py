import json
from pathlib import Path

import boto3
from botocore.exceptions import ClientError


def run_verification(user: str, lab: str, email: str, **provider_config) -> dict:
    region = provider_config["region"]
    account_id = provider_config["account_id"]

    try:
        spec_path = Path(__file__).parent / "lab_spec.json"
        with open(spec_path, "r", encoding="utf-8") as file:
            spec = json.load(file)

        checks = spec["checks"]
        rds = boto3.client("rds", region_name=region)
        sts = boto3.client("sts", region_name=region)

        try:
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
        except ClientError as error:
            return {"success": False, "message": f"AWS hiba történt: {error}"}
    except Exception as error:
        return {"success": False, "message": str(error)}
