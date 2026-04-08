import json
from pathlib import Path

from google.api_core.exceptions import NotFound
from google.cloud import compute_v1


def run_verification(user: str, lab: str, email: str, **provider_config) -> dict:
    project_id = provider_config["project_id"]

    try:
        spec_path = Path(__file__).parent / "lab_spec.json"
        with open(spec_path, "r", encoding="utf-8") as file:
            spec = json.load(file)

        checks = spec["checks"]
        instances_client = compute_v1.InstancesClient()
        networks_client = compute_v1.NetworksClient()

        try:
            instance_spec = checks["instance"]
            matching_instances = []

            for _, scoped_list in instances_client.aggregated_list(project=project_id):
                for instance in scoped_list.instances or []:
                    if instance.name.startswith(instance_spec["prefix"]):
                        matching_instances.append(instance)

            if len(matching_instances) < instance_spec["count"]:
                return {
                    "success": False,
                    "message": (
                        f"Nem található elegendő GCP instance, amely "
                        f"'{instance_spec['prefix']}' prefixszel kezdődik. "
                        f"Elvárt: {instance_spec['count']}, Talált: {len(matching_instances)}"
                    ),
                }

            for instance in matching_instances:
                machine_type = instance.machine_type.split("/")[-1]
                if machine_type != instance_spec["machine_type"]:
                    return {
                        "success": False,
                        "message": (
                            f"GCP instance típusa hibás: {instance.name} - {machine_type}"
                        ),
                    }

            network_spec = checks["network"]
            matching_network = next(
                (
                    network
                    for network in networks_client.list(project=project_id)
                    if network.name.startswith(network_spec["prefix"])
                ),
                None,
            )

            if not matching_network:
                return {
                    "success": False,
                    "message": (
                        f"Nem található olyan VPC hálózat, amely "
                        f"'{network_spec['prefix']}' prefixszel kezdődik."
                    ),
                }

            return {"success": True, "message": "Lab sikeresen ellenőrizve."}
        except NotFound:
            return {
                "success": False,
                "message": f"A GCP projekt nem található: {project_id}.",
            }
    except Exception as error:
        return {"success": False, "message": str(error)}
