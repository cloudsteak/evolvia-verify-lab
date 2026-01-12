import json
from pathlib import Path
from azure.identity import DefaultAzureCredential
from azure.mgmt.search import SearchManagementClient
from azure.core.exceptions import ResourceNotFoundError
import logging


def run_verification(user: str, lab: str, email: str, subscription_id: str) -> dict:
    try:
        resource_group = f"{user}"
        spec_path = Path(__file__).parent / "lab_spec.json"

        with open(spec_path, "r", encoding="utf-8") as f:
            spec = json.load(f)

        checks = spec["checks"]
        credential = DefaultAzureCredential()
        search_mgmt = SearchManagementClient(credential, subscription_id)

        # ✅ Search Service ellenőrzés
        search_spec = checks["search"]
        try:
            # Listázd az összes Search Service-t a resource groupban
            search_services = search_mgmt.services.list_by_resource_group(resource_group)
            matching_services = [s for s in search_services if s.name.startswith(search_spec["prefix"])]

            # Ellenőrizd, hogy a megfelelő számú Search Service létezik-e
            if len(matching_services) < search_spec["count"]:
                return {
                    "success": False,
                    "message": f"Nem található elegendő Search Service, amely '{search_spec['prefix']}' prefixszel kezdődik a resource groupban '{resource_group}'. Elvárt: {search_spec['count']}, Talált: {len(matching_services)}",
                }

            # Ellenőrizd az index létezését a Search Service-ben
            for service in matching_services:
                service_name = service.name
                
                # Szerezd meg a Search Service admin kulcsát
                admin_keys = search_mgmt.admin_keys.get(resource_group, service_name)
                primary_key = admin_keys.primary_key

                # Ellenőrizd az indexet a Search REST API-val
                from azure.core.credentials import AzureKeyCredential
                from azure.search.documents.indexes import SearchIndexClient

                index_client = SearchIndexClient(
                    endpoint=f"https://{service_name}.search.windows.net",
                    credential=AzureKeyCredential(primary_key)
                )

                try:
                    # Próbáld meg lekérni az indexet
                    index = index_client.get_index(search_spec["index"])
                    if not index:
                        return {
                            "success": False,
                            "message": f"Az index '{search_spec['index']}' nem található a Search Service-ben '{service_name}'.",
                        }
                except Exception as e:
                    return {
                        "success": False,
                        "message": f"Az index '{search_spec['index']}' nem található a Search Service-ben '{service_name}'. Hiba: {str(e)}",
                    }

        except ResourceNotFoundError:
            return {
                "success": False,
                "message": f"Search Service nem található a resource groupban '{resource_group}'.",
            }

        return {"success": True, "message": "Lab sikeresen ellenőrizve."}

    except Exception as e:
        # Bármilyen más hiba szép JSON válaszként
        return {"success": False, "message": str(e)}
