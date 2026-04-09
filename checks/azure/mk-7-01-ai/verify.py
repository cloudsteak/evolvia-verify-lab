import json
from pathlib import Path

from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.mgmt.search import SearchManagementClient
from azure.search.documents.indexes import SearchIndexClient


def run_verification(user: str, lab: str, email: str, **provider_config) -> dict:
    subscription_id = provider_config["subscription_id"]

    try:
        resource_group = user
        spec_path = Path(__file__).parent / "lab_spec.json"

        with open(spec_path, "r", encoding="utf-8") as file:
            spec = json.load(file)

        checks = spec["checks"]
        credential = DefaultAzureCredential()
        search_mgmt = SearchManagementClient(credential, subscription_id)

        search_spec = checks["search"]
        try:
            search_services = search_mgmt.services.list_by_resource_group(resource_group)
            matching_services = [
                service
                for service in search_services
                if service.name.startswith(search_spec["prefix"])
            ]

            if len(matching_services) < search_spec["count"]:
                return {
                    "success": False,
                    "message": (
                        f"Nem található elegendő Search Service, amely "
                        f"'{search_spec['prefix']}' prefixszel kezdődik a resource "
                        f"groupban '{resource_group}'. Elvárt: {search_spec['count']}, "
                        f"Talált: {len(matching_services)}"
                    ),
                }

            for service in matching_services:
                admin_keys = search_mgmt.admin_keys.get(resource_group, service.name)
                index_client = SearchIndexClient(
                    endpoint=f"https://{service.name}.search.windows.net",
                    credential=AzureKeyCredential(admin_keys.primary_key),
                )

                try:
                    index = index_client.get_index(search_spec["index"])
                    if not index:
                        return {
                            "success": False,
                            "message": (
                                f"Az index '{search_spec['index']}' nem található a "
                                f"Search Service-ben '{service.name}'."
                            ),
                        }
                except Exception as error:
                    return {
                        "success": False,
                        "message": (
                            f"Az index '{search_spec['index']}' nem található a "
                            f"Search Service-ben '{service.name}'. Hiba: {error}"
                        ),
                    }
        except ResourceNotFoundError:
            return {
                "success": False,
                "message": (
                    f"Search Service nem található a resource groupban "
                    f"'{resource_group}'."
                ),
            }

        return {"success": True, "message": "Lab sikeresen ellenőrizve."}
    except Exception as error:
        return {"success": False, "message": str(error)}
