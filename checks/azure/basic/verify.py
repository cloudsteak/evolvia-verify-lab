import json
from pathlib import Path

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

        return {"success": True, "message": "Lab sikeresen ellenőrizve."}
    except Exception as error:
        return {"success": False, "message": str(error)}
