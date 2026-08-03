import logging
import os

import azure.functions as func
from labs.registry import run_lab
from shared.responses import json_response
from shared.validation import validate_verify_body

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO").upper())

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


@app.route(route="health", methods=["GET"])
def health(_req: func.HttpRequest) -> func.HttpResponse:
    return json_response({"status": "ok"})


@app.route(route="dispatcher", methods=["POST"])
def dispatcher(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json()
    except ValueError:
        return json_response(
            {"success": False, "message": "Érvénytelen JSON törzs."},
            status_code=400,
        )

    if not isinstance(body, dict):
        return json_response(
            {"success": False, "message": "Érvénytelen JSON törzs."},
            status_code=400,
        )

    error = validate_verify_body(body)
    if error:
        logger.warning("Validációs hiba: %s", error)
        return json_response({"success": False, "message": error}, status_code=400)

    cloud = str(body["cloud"]).strip().lower()
    if cloud != "azure":
        return json_response(
            {
                "success": False,
                "message": (
                    f"A '{cloud}' szolgáltató nem támogatott ebben a környezetben. "
                    "Az aktív szolgáltató: 'azure'."
                ),
            },
            status_code=400,
        )

    lab = str(body["lab"]).strip().lower()
    user = str(body["user"]).strip()
    email = str(body["email"]).strip()

    logger.info("Dispatching: user=%s lab=%s", user, lab)

    result = run_lab(lab=lab, user=user, email=email)
    status_code = 404 if not result.get("success") and "Ismeretlen lab" in result.get("message", "") else 200

    logger.info(
        "Kérés lezárva: user=%s lab=%s success=%s",
        user,
        lab,
        result.get("success"),
    )
    return json_response(result, status_code=status_code)
