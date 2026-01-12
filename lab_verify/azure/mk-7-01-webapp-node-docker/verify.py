import json
from pathlib import Path
from azure.identity import DefaultAzureCredential
from azure.mgmt.web import WebSiteManagementClient
from azure.core.exceptions import ResourceNotFoundError
import logging
import requests


def run_verification(user: str, lab: str, email: str, subscription_id: str) -> dict:
    try:
        resource_group = f"{user}"
        spec_path = Path(__file__).parent / "lab_spec.json"

        with open(spec_path, "r", encoding="utf-8") as f:
            spec = json.load(f)

        checks = spec["checks"]
        credential = DefaultAzureCredential()
        web_client = WebSiteManagementClient(credential, subscription_id)

        # ✅ Web App ellenőrzés
        webapp_spec = checks["webapp"]
        app_service_plan_spec = checks.get("app_service_plan")
        
        try:
            # Listázd az összes Web App-ot a resource groupban
            webapps = web_client.web_apps.list_by_resource_group(resource_group)
            matching_webapps = [w for w in webapps if w.name.startswith(webapp_spec["prefix"])]

            # Ellenőrizd, hogy a megfelelő számú Web App létezik-e
            if len(matching_webapps) < webapp_spec["count"]:
                return {
                    "success": False,
                    "message": f"Nem található elegendő Web App, amely '{webapp_spec['prefix']}' prefixszel kezdődik a resource groupban '{resource_group}'. Elvárt: {webapp_spec['count']}, Talált: {len(matching_webapps)}",
                }

            # Ellenőrizd az egyes Web App-ok Docker konfigurációját és App Service Plan-ját
            for webapp in matching_webapps:
                # Szerezd meg a Web App konfigurációját
                config = web_client.web_apps.get_configuration(
                    resource_group_name=resource_group,
                    name=webapp.name
                )

                # Ellenőrizd, hogy Docker konténerből fut-e
                linux_fx_version = config.linux_fx_version
                
                if not linux_fx_version:
                    return {
                        "success": False,
                        "message": f"Web App '{webapp.name}' nem rendelkezik Linux FX verzióval (Docker konfiguráció hiányzik).",
                    }

                # Docker konténer ellenőrzés
                # Lehetséges formátumok:
                # 1. DOCKER|<registry>.azurecr.io/<image>:<tag> - direkt ACR image megadás
                # 2. "sitecontainers" - Azure Deployment Center használata ACR-ből
                
                is_docker_direct = linux_fx_version.upper().startswith("DOCKER|")
                is_sitecontainers = linux_fx_version.lower() == "sitecontainers"
                
                if not (is_docker_direct or is_sitecontainers):
                    return {
                        "success": False,
                        "message": f"Web App '{webapp.name}' nem Docker konténerből fut. Linux FX Version: {linux_fx_version}",
                    }

                # Ha DOCKER| prefixszel kezdődik, ellenőrizzük hogy van-e benne registry
                if is_docker_direct:
                    docker_image = linux_fx_version[7:]  # "DOCKER|" prefix eltávolítása
                    
                    # Elfogadjuk mind az ACR (.azurecr.io), mind más registry-ket
                    if "/" not in docker_image:
                        return {
                            "success": False,
                            "message": f"Web App '{webapp.name}' Docker image formátuma hibás: {docker_image}",
                        }
                
                # Ha "sitecontainers", az Azure Deployment Center-t használja, ami OK

                # ✅ App Service Plan SKU ellenőrzés
                if app_service_plan_spec:
                    # Szerezd meg az App Service Plan-t
                    app_service_plan_id = webapp.server_farm_id
                    # Az ID formátuma: /subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Web/serverfarms/{name}
                    plan_name = app_service_plan_id.split('/')[-1]
                    
                    try:
                        plan = web_client.app_service_plans.get(
                            resource_group_name=resource_group,
                            name=plan_name
                        )
                        
                        actual_sku = plan.sku.name
                        expected_sku = app_service_plan_spec["sku"]
                        
                        if actual_sku.upper() != expected_sku.upper():
                            return {
                                "success": False,
                                "message": f"App Service Plan SKU hibás: {plan_name} - {actual_sku}. Elvárt: {expected_sku}",
                            }
                    except Exception as plan_error:
                        return {
                            "success": False,
                            "message": f"Nem sikerült lekérni az App Service Plan-t: {plan_name}. Hiba: {str(plan_error)}",
                        }

                # ✅ Web App URL ellenőrzés - elérhetőség tesztelése
                webapp_url = f"https://{webapp.default_host_name}"
                try:
                    response = requests.get(webapp_url, timeout=10, allow_redirects=True)
                    if response.status_code >= 500:
                        return {
                            "success": False,
                            "message": f"Web App ({webapp.name}) elérhető, de szerver hibát ad vissza: {response.status_code}. URL: {webapp_url}",
                        }
                    # 200-499 közötti státusz kódok OK-nak számítanak (működik az alkalmazás)
                except requests.exceptions.Timeout:
                    return {
                        "success": False,
                        "message": f"Web App ({webapp.name}) nem válaszol időben. URL: {webapp_url}",
                    }
                except requests.exceptions.ConnectionError:
                    return {
                        "success": False,
                        "message": f"Web App ({webapp.name}) nem elérhető. URL: {webapp_url}",
                    }
                except Exception as http_error:
                    return {
                        "success": False,
                        "message": f"Web App ({webapp.name}) HTTP ellenőrzés sikertelen. URL: {webapp_url}. Hiba: {str(http_error)}",
                    }

        except ResourceNotFoundError:
            return {
                "success": False,
                "message": f"Web App nem található a resource groupban '{resource_group}'.",
            }

        # Minden ellenőrzés sikeres
        return {"success": True, "message": "Lab sikeresen ellenőrizve."}

    except Exception as e:
        # Bármilyen más hiba szép JSON válaszként
        logging.error(f"Hiba történt a verifikáció során: {str(e)}", exc_info=True)
        return {"success": False, "message": str(e)}
