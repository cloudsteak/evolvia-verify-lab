import json
from pathlib import Path
from azure.identity import DefaultAzureCredential
from azure.mgmt.compute import ComputeManagementClient
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
        compute = ComputeManagementClient(credential, subscription_id)

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

        return {"success": True, "message": "Lab sikeresen ellenőrizve."}

    except Exception as e:
        # Bármilyen más hiba szép JSON válaszként
        return {"success": False, "message": str(e)}
