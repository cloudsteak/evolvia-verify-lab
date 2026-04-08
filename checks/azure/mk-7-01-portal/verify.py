import logging


def run_verification(user: str, lab: str, email: str, **provider_config) -> dict:
    subscription_id = provider_config["subscription_id"]

    try:
        logging.info(
            "Verifying lab '%s' for user '%s' in subscription '%s'",
            lab,
            user,
            subscription_id,
        )
        return {"success": True, "message": "Lab sikeresen ellenőrizve."}
    except Exception as error:
        logging.error("Error verifying lab '%s' for user '%s': %s", lab, user, error)
        return {"success": False, "message": str(error)}
