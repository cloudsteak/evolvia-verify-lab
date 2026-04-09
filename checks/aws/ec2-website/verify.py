import json
from pathlib import Path

import boto3
import requests
from botocore.exceptions import ClientError


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
                    },
                    {
                        "Name": "instance-state-name",
                        "Values": ["running"],
                    },
                ]
            )["Reservations"]
            instances = [
                instance
                for reservation in reservations
                for instance in reservation["Instances"]
            ]

            if len(instances) < instance_spec["count"]:
                return {
                    "success": False,
                    "message": (
                        f"Nem található elegendő futó EC2 instance, amely "
                        f"'{instance_spec['prefix']}' prefixszel kezdődik. "
                        f"Elvárt: {instance_spec['count']}, Talált: {len(instances)}"
                    ),
                }

            expected_status_codes = set(checks["website"]["expected_status_codes"])
            port = checks["website"]["port"]

            for instance in instances:
                if instance["InstanceType"] != instance_spec["instance_type"]:
                    return {
                        "success": False,
                        "message": (
                            f"EC2 instance típusa hibás: "
                            f"{instance['InstanceId']} - {instance['InstanceType']}"
                        ),
                    }

                host = instance.get("PublicDnsName") or instance.get("PublicIpAddress")
                if not host:
                    return {
                        "success": False,
                        "message": (
                            f"Az EC2 instance nem rendelkezik nyilvános címmel: "
                            f"{instance['InstanceId']}"
                        ),
                    }

                try:
                    response = requests.get(
                        f"http://{host}:{port}",
                        timeout=10,
                        allow_redirects=False,
                    )
                except requests.RequestException as error:
                    return {
                        "success": False,
                        "message": (
                            f"A weboldal nem érhető el a {port}-as porton. "
                            f"Instance: {instance['InstanceId']}. Hiba: {error}"
                        ),
                    }

                if response.status_code not in expected_status_codes:
                    return {
                        "success": False,
                        "message": (
                            f"A weboldal hibás HTTP státuszkódot ad vissza: "
                            f"{response.status_code}. Instance: {instance['InstanceId']}"
                        ),
                    }

            return {"success": True, "message": "Lab sikeresen ellenőrizve."}
        except ClientError as error:
            return {"success": False, "message": f"AWS hiba történt: {error}"}
    except Exception as error:
        return {"success": False, "message": str(error)}
