import json
from pathlib import Path

import requests
from azure.core.exceptions import ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.network import NetworkManagementClient


def run_verification(user: str, lab: str, email: str, **provider_config) -> dict:
    subscription_id = provider_config["subscription_id"]

    try:
        resource_group = user
        spec_path = Path(__file__).parent / "lab_spec.json"

        with open(spec_path, "r", encoding="utf-8") as file:
            spec = json.load(file)

        checks = spec["checks"]
        credential = DefaultAzureCredential()
        compute = ComputeManagementClient(credential, subscription_id)
        network = NetworkManagementClient(credential, subscription_id)

        vm_spec = checks["vm"]
        try:
            vms = compute.virtual_machines.list(resource_group)
            matching_vms = [vm for vm in vms if vm.name.startswith(vm_spec["prefix"])]

            if len(matching_vms) < vm_spec["count"]:
                return {
                    "success": False,
                    "message": (
                        f"Nem található elegendő VM, amely '{vm_spec['prefix']}' "
                        f"prefixszel kezdődik a resource groupban '{resource_group}'. "
                        f"Elvárt: {vm_spec['count']}, Talált: {len(matching_vms)}"
                    ),
                }

            for vm in matching_vms:
                if vm.hardware_profile.vm_size != vm_spec["size"]:
                    return {
                        "success": False,
                        "message": f"VM méret hibás: {vm.name} - {vm.hardware_profile.vm_size}",
                    }

                if vm.storage_profile.os_disk.os_type != vm_spec["os_type"]:
                    return {
                        "success": False,
                        "message": (
                            f"OS típus hibás: "
                            f"{vm.name} - {vm.storage_profile.os_disk.os_type}"
                        ),
                    }
        except ResourceNotFoundError:
            return {
                "success": False,
                "message": f"VM nem található a resource groupban '{resource_group}'.",
            }

        vnet_spec = checks["vnet"]
        try:
            vnets = network.virtual_networks.list(resource_group)
            vnet = next(
                (item for item in vnets if item.name.startswith(vnet_spec["prefix"])),
                None,
            )

            if not vnet:
                return {
                    "success": False,
                    "message": (
                        f"Nem található olyan VNet, amely '{vnet_spec['prefix']}' "
                        f"prefixszel kezdődik a resource groupban '{resource_group}'."
                    ),
                }
        except ResourceNotFoundError:
            return {
                "success": False,
                "message": f"VNet nem található a resource groupban '{resource_group}'.",
            }

        if not vnet.name.startswith(vnet_spec["prefix"]):
            return {"success": False, "message": f"VNet neve hibás: {vnet.name}"}

        lb_spec = checks["lb"]
        try:
            lbs = network.load_balancers.list(resource_group)
            lb = next((item for item in lbs if item.name.startswith(lb_spec["prefix"])), None)

            if not lb:
                return {
                    "success": False,
                    "message": (
                        f"Nem található olyan Load Balancer, amely "
                        f"'{lb_spec['prefix']}' prefixszel kezdődik a resource "
                        f"groupban '{resource_group}'."
                    ),
                }

            if lb_spec.get("sku") and lb.sku.name.lower() != lb_spec["sku"].lower():
                return {
                    "success": False,
                    "message": (
                        f"Load Balancer SKU hibás: {lb.sku.name}. "
                        f"Elvárt: {lb_spec['sku']}."
                    ),
                }

            frontend_ip_configurations = lb.frontend_ip_configurations
            if not frontend_ip_configurations:
                return {
                    "success": False,
                    "message": (
                        f"A Load Balancer '{lb.name}' nem rendelkezik frontend IP "
                        f"konfigurációval."
                    ),
                }

            frontend_ip_config = frontend_ip_configurations[0]
            frontend_ip = None

            if frontend_ip_config.public_ip_address:
                public_ip_id = frontend_ip_config.public_ip_address.id
                public_ip_name = public_ip_id.split("/")[-1]
                public_ip_details = network.public_ip_addresses.get(
                    resource_group_name=resource_group,
                    public_ip_address_name=public_ip_name,
                )

                if public_ip_details.ip_address:
                    frontend_ip = public_ip_details.ip_address
                else:
                    return {
                        "success": False,
                        "message": (
                            f"A Load Balancer '{lb.name}' public IP-címe nem található. "
                            f"Ellenőrizd az Azure konfigurációt."
                        ),
                    }
            elif frontend_ip_config.private_ip_address:
                frontend_ip = frontend_ip_config.private_ip_address
            else:
                return {
                    "success": False,
                    "message": (
                        f"A Load Balancer '{lb.name}' nem rendelkezik érvényes frontend "
                        f"IP-címmel."
                    ),
                }

            try:
                response = requests.get(f"http://{frontend_ip}:80", timeout=10)
                if response.status_code != 200:
                    return {
                        "success": False,
                        "message": (
                            f"A Load Balancer '{lb.name}' nem érhető el a 80-as porton. "
                            f"HTTP státuszkód: {response.status_code}"
                        ),
                    }
            except requests.RequestException as error:
                return {
                    "success": False,
                    "message": (
                        f"A Load Balancer '{lb.name}' nem érhető el a 80-as porton. "
                        f"Hiba: {error}"
                    ),
                }
        except ResourceNotFoundError:
            return {
                "success": False,
                "message": (
                    f"Load Balancer nem található a resource groupban "
                    f"'{resource_group}'."
                ),
            }

        return {"success": True, "message": "Lab sikeresen ellenőrizve."}
    except Exception as error:
        return {"success": False, "message": str(error)}
