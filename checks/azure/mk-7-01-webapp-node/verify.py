import json
import logging
from pathlib import Path

import requests
from azure.core.exceptions import ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.mgmt.web import WebSiteManagementClient


def run_verification(user: str, lab: str, email: str, **provider_config) -> dict:
    subscription_id = provider_config["subscription_id"]

    try:
        resource_group = user
        spec_path = Path(__file__).parent / "lab_spec.json"

        with open(spec_path, "r", encoding="utf-8") as file:
            spec = json.load(file)

        checks = spec["checks"]
        credential = DefaultAzureCredential()
        web_client = WebSiteManagementClient(credential, subscription_id)

        webapp_spec = checks["webapp"]
        app_service_plan_spec = checks.get("app_service_plan")

        try:
            webapps = web_client.web_apps.list_by_resource_group(resource_group)
            matching_webapps = [
                webapp
                for webapp in webapps
                if webapp.name.startswith(webapp_spec["prefix"])
            ]

            if len(matching_webapps) < webapp_spec["count"]:
                return {
                    "success": False,
                    "message": (
                        f"Nem található elegendő Web App, amely "
                        f"'{webapp_spec['prefix']}' prefixszel kezdődik a resource "
                        f"groupban '{resource_group}'. Elvárt: {webapp_spec['count']}, "
                        f"Talált: {len(matching_webapps)}"
                    ),
                }

            for webapp in matching_webapps:
                config = web_client.web_apps.get_configuration(
                    resource_group_name=resource_group,
                    name=webapp.name,
                )

                actual_runtime = (
                    config.linux_fx_version
                    if config.linux_fx_version
                    else config.windows_fx_version
                )

                if not actual_runtime:
                    return {
                        "success": False,
                        "message": (
                            f"Web App '{webapp.name}' nem rendelkezik runtime stack-kel."
                        ),
                    }

                expected_runtime = webapp_spec["runtime_stack"].upper()
                if expected_runtime not in actual_runtime.upper():
                    return {
                        "success": False,
                        "message": (
                            f"Web App runtime stack hibás: {webapp.name} - "
                            f"{actual_runtime}. Elvárt (tartalmazza): "
                            f"{webapp_spec['runtime_stack']}"
                        ),
                    }

                if app_service_plan_spec:
                    app_service_plan_id = webapp.server_farm_id
                    plan_name = app_service_plan_id.split("/")[-1]

                    try:
                        plan = web_client.app_service_plans.get(
                            resource_group_name=resource_group,
                            name=plan_name,
                        )

                        actual_sku = plan.sku.name
                        expected_sku = app_service_plan_spec["sku"]

                        if actual_sku.upper() != expected_sku.upper():
                            return {
                                "success": False,
                                "message": (
                                    f"App Service Plan SKU hibás: {plan_name} - "
                                    f"{actual_sku}. Elvárt: {expected_sku}"
                                ),
                            }
                    except Exception as error:
                        return {
                            "success": False,
                            "message": (
                                f"Nem sikerült lekérni az App Service Plan-t: "
                                f"{plan_name}. Hiba: {error}"
                            ),
                        }

                webapp_url = f"https://{webapp.default_host_name}"
                try:
                    response = requests.get(
                        webapp_url, timeout=10, allow_redirects=True
                    )
                    if response.status_code >= 500:
                        return {
                            "success": False,
                            "message": (
                                f"Web App ({webapp.name}) elérhető, de szerver hibát ad "
                                f"vissza: {response.status_code}. URL: {webapp_url}"
                            ),
                        }
                except requests.exceptions.Timeout:
                    return {
                        "success": False,
                        "message": (
                            f"Web App ({webapp.name}) nem válaszol időben. "
                            f"URL: {webapp_url}"
                        ),
                    }
                except requests.exceptions.ConnectionError:
                    return {
                        "success": False,
                        "message": (
                            f"Web App ({webapp.name}) nem elérhető. URL: {webapp_url}"
                        ),
                    }
                except Exception as error:
                    return {
                        "success": False,
                        "message": (
                            f"Web App ({webapp.name}) HTTP ellenőrzés sikertelen. "
                            f"URL: {webapp_url}. Hiba: {error}"
                        ),
                    }
        except ResourceNotFoundError:
            return {
                "success": False,
                "message": f"Web App nem található a resource groupban '{resource_group}'.",
            }

        return {"success": True, "message": "Lab sikeresen ellenőrizve."}
    except Exception as error:
        logging.error("Verification failed: %s", error, exc_info=True)
        return {"success": False, "message": str(error)}
