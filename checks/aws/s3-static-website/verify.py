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
        s3 = boto3.client("s3", region_name=region)
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

            bucket_spec = checks["bucket"]
            buckets = s3.list_buckets()["Buckets"]
            matching_buckets = [
                bucket
                for bucket in buckets
                if bucket["Name"].startswith(bucket_spec["prefix"])
            ]

            if len(matching_buckets) < bucket_spec["count"]:
                return {
                    "success": False,
                    "message": (
                        f"Nem található elegendő S3 bucket, amely "
                        f"'{bucket_spec['prefix']}' prefixszel kezdődik. "
                        f"Elvárt: {bucket_spec['count']}, Talált: {len(matching_buckets)}"
                    ),
                }

            expected_index_document = checks["website"]["index_document"]
            for bucket in matching_buckets:
                bucket_name = bucket["Name"]
                location_response = s3.get_bucket_location(Bucket=bucket_name)
                bucket_region = location_response.get("LocationConstraint") or "us-east-1"

                if bucket_region != region:
                    continue

                website_config = s3.get_bucket_website(Bucket=bucket_name)
                actual_index_document = (
                    website_config.get("IndexDocument") or {}
                ).get("Suffix")

                if actual_index_document != expected_index_document:
                    return {
                        "success": False,
                        "message": (
                            f"Az S3 static website index dokumentuma hibás: "
                            f"{bucket_name} - {actual_index_document}. "
                            f"Elvárt: {expected_index_document}"
                        ),
                    }

                return {"success": True, "message": "Lab sikeresen ellenőrizve."}

            return {
                "success": False,
                "message": (
                    f"Nem található olyan S3 bucket a '{region}' régióban, amely "
                    f"'{bucket_spec['prefix']}' prefixszel kezdődik."
                ),
            }
        except ClientError as error:
            return {"success": False, "message": f"AWS hiba történt: {error}"}
    except Exception as error:
        return {"success": False, "message": str(error)}
