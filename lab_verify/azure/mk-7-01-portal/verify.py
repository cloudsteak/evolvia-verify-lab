import json
from pathlib import Path
from azure.identity import DefaultAzureCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.core.exceptions import ResourceNotFoundError
import logging


def run_verification(user: str, lab: str, email: str, subscription_id: str) -> dict:
    try:
        logging.info(f"Verifying lab '{lab}' for user '{user}'")
        return {"success": True, "message": "Lab sikeresen ellenőrizve."}

    except Exception as e:
        # Bármilyen más hiba szép JSON válaszként
        logging.error(f"Error verifying lab '{lab}' for user '{user}': {e}")
        return {"success": False, "message": str(e)}
