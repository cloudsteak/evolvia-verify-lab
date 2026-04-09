import json
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


def run_verification(user: str, lab: str, email: str, **provider_config) -> dict:
    region = provider_config["region"]
    account_id = provider_config["account_id"]

    try:
        spec_path = Path(__file__).parent / "lab_spec.json"
        with open(spec_path, "r", encoding="utf-8") as file:
            spec = json.load(file)

        checks = spec["checks"]
        ec2 = boto3.client("ec2", region_name=region)
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

            instance_spec = checks["instance"]
            reservations = ec2.describe_instances(
                Filters=[
                    {
                        "Name": "tag:Name",
                        "Values": [f"{instance_spec['prefix']}*"],
                    }
                ]
            )["Reservations"]
            instances = [
                instance
                for reservation in reservations
                for instance in reservation["Instances"]
                if instance.get("State", {}).get("Name")
                not in {"terminated", "shutting-down"}
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

            vpc_spec = checks["vpc"]
            vpcs = ec2.describe_vpcs()["Vpcs"]
            matching_vpc = next(
                (
                    vpc
                    for vpc in vpcs
                    if (_get_name_tag(vpc.get("Tags")) or "").startswith(
                        vpc_spec["prefix"]
                    )
                ),
                None,
            )

            if not matching_vpc:
                return {
                    "success": False,
                    "message": (
                        f"Nem található olyan VPC, amely "
                        f"'{vpc_spec['prefix']}' prefixszel kezdődik."
                    ),
                }

            return {"success": True, "message": "Lab sikeresen ellenőrizve."}
        except ClientError as error:
            return {"success": False, "message": f"AWS hiba történt: {error}"}
    except Exception as error:
        return {"success": False, "message": str(error)}
