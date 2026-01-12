import json
from pathlib import Path
from azure.identity import DefaultAzureCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.core.exceptions import ResourceNotFoundError
import logging

from fastapi import requests


def run_verification(user: str, lab: str, email: str, subscription_id: str) -> dict:
    try:
        resource_group = f"{user}"
        spec_path = Path(__file__).parent / "lab_spec.json"

        with open(spec_path, "r", encoding="utf-8") as f:
            spec = json.load(f)

        checks = spec["checks"]
        credential = DefaultAzureCredential()
        compute = ComputeManagementClient(credential, subscription_id)
        network = NetworkManagementClient(credential, subscription_id)

        # ✅ VM ellenőrzés
        vm_spec = checks["vm"]
        try:
            # Listázd az összes VM-et a resource groupban
            vms = compute.virtual_machines.list(resource_group)
            matching_vms = [v for v in vms if v.name.startswith(vm_spec["prefix"])]

            # Ellenőrizd, hogy a megfelelő számú VM létezik-e
            if len(matching_vms) < vm_spec["count"]:
                return {
                    "success": False,
                    "message": f"Nem található elegendő VM, amely '{vm_spec['prefix']}' prefixszel kezdődik a resource groupban '{resource_group}'. Elvárt: {vm_spec['count']}, Talált: {len(matching_vms)}",
                }

            # Ellenőrizd az egyes VM-ek méretét és OS típusát
            for vm in matching_vms:
                if vm.hardware_profile.vm_size != vm_spec["size"]:
                    return {
                        "success": False,
                        "message": f"VM méret hibás: {vm.name} - {vm.hardware_profile.vm_size}",
                    }

                if vm.storage_profile.os_disk.os_type != vm_spec["os_type"]:
                    return {
                        "success": False,
                        "message": f"OS típus hibás: {vm.name} - {vm.storage_profile.os_disk.os_type}",
                    }

        except ResourceNotFoundError:
            return {
                "success": False,
                "message": f"VM nem található a resource groupban '{resource_group}'.",
            }

        # ✅ VNet ellenőrzés
        vnet_spec = checks["vnet"]
        try:
            # Listázd az összes VNet-et a resource groupban
            vnets = network.virtual_networks.list(resource_group)
            vnet = next(
                (v for v in vnets if v.name.startswith(vnet_spec["prefix"])), None
            )

            if not vnet:
                return {
                    "success": False,
                    "message": f"Nem található olyan VNet, amely '{vnet_spec['prefix']}' prefixszel kezdődik a resource groupban '{resource_group}'.",
                }
        except ResourceNotFoundError:
            return {
                "success": False,
                "message": f"VNet nem található a resource groupban '{resource_group}'.",
            }

        # Ellenőrizd, hogy a VNet neve helyes prefixszel kezdődik-e
        if not vnet.name.startswith(vnet_spec["prefix"]):
            return {"success": False, "message": f"VNet neve hibás: {vnet.name}"}

        # ✅ Load Balancer ellenőrzés
        lb_spec = checks["lb"]
        try:
            # Listázd az összes Load Balancer-t a resource groupban
            lbs = network.load_balancers.list(resource_group)
            lb = next((l for l in lbs if l.name.startswith(lb_spec["prefix"])), None)

            if not lb:
                return {
                    "success": False,
                    "message": f"Nem található olyan Load Balancer, amely '{lb_spec['prefix']}' prefixszel kezdődik a resource groupban '{resource_group}'.",
                }

            # Ellenőrizd a Load Balancer termékváltozatát (SKU)
            if lb_spec.get("sku") and lb.sku.name.lower() != lb_spec["sku"].lower():
                return {
                    "success": False,
                    "message": f"Load Balancer SKU hibás: {lb.sku.name}. Elvárt: {lb_spec['sku']}.",
                }

            # Ellenőrizd a Load Balancer típusát (Public vagy Internal)
            frontend_ip_configurations = lb.frontend_ip_configurations
            if not frontend_ip_configurations:
                return {
                    "success": False,
                    "message": f"A Load Balancer '{lb.name}' nem rendelkezik frontend IP konfigurációval.",
                }

            # Szerezd meg a Load Balancer frontend IP-címét
            frontend_ip_configurations = lb.frontend_ip_configurations
            if not frontend_ip_configurations:
                return {
                    "success": False,
                    "message": f"A Load Balancer '{lb.name}' nem rendelkezik frontend IP konfigurációval.",
                }

            # Az első frontend IP-cím használata
            frontend_ip_config = frontend_ip_configurations[0]
            frontend_ip = None

            # Ellenőrizd, hogy van-e public vagy private IP-cím
            if frontend_ip_config.public_ip_address:
                # Szerezd meg a public IP-cím erőforrásazonosítóját
                public_ip_id = frontend_ip_config.public_ip_address.id

                # Kérjük le a public IP-cím részleteit az Azure-ból
                public_ip_name = public_ip_id.split("/")[
                    -1
                ]  # Az ID utolsó része a public IP-cím neve
                public_ip_details = network.public_ip_addresses.get(
                    resource_group_name=resource_group,
                    public_ip_address_name=public_ip_name,
                )

                # Ellenőrizzük, hogy van-e IP-cím
                if public_ip_details.ip_address:
                    frontend_ip = public_ip_details.ip_address
                else:
                    return {
                        "success": False,
                        "message": f"A Load Balancer '{lb.name}' public IP-címe nem található. Ellenőrizd az Azure konfigurációt.",
                    }
            elif frontend_ip_config.private_ip_address:
                frontend_ip = frontend_ip_config.private_ip_address
            else:
                return {
                    "success": False,
                    "message": f"A Load Balancer '{lb.name}' nem rendelkezik érvényes frontend IP-címmel.",
                }

            # Hívjuk meg a Load Balancer IP-címét a 80-as porton
            import requests

            try:
                response = requests.get(f"http://{frontend_ip}:80")
                if response.status_code != 200:
                    return {
                        "success": False,
                        "message": f"A Load Balancer '{lb.name}' nem érhető el a 80-as porton. HTTP státuszkód: {response.status_code}",
                    }
            except requests.RequestException as e:
                return {
                    "success": False,
                    "message": f"A Load Balancer '{lb.name}' nem érhető el a 80-as porton. Hiba: {str(e)}",
                }

        except ResourceNotFoundError:
            return {
                "success": False,
                "message": f"Load Balancer nem található a resource groupban '{resource_group}'.",
            }

        # Minden ellenőrzés sikeres
        return {"success": True, "message": "Lab sikeresen ellenőrizve."}

    except Exception as e:
        # Bármilyen más hiba szép JSON válaszként
        return {"success": False, "message": str(e)}
