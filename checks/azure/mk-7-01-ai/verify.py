import json
from pathlib import Path

import requests
from azure.identity import DefaultAzureCredential

ARM_API_VERSION = "2025-06-01"
AGENTS_API_VERSION = "v1"
ARM_SCOPE = "https://management.azure.com/.default"
FOUNDRY_SCOPE = "https://ai.azure.com/.default"


def run_verification(user: str, lab: str, email: str, **provider_config) -> dict:
    subscription_id = provider_config["subscription_id"]

    try:
        resource_group = user
        spec_path = Path(__file__).parent / "lab_spec.json"

        with open(spec_path, "r", encoding="utf-8") as file:
            spec = json.load(file)

        foundry_spec = spec["checks"]["foundry"]
        credential = DefaultAzureCredential()
        arm_token = credential.get_token(ARM_SCOPE).token

        accounts_url = (
            f"https://management.azure.com/subscriptions/{subscription_id}"
            f"/resourceGroups/{resource_group}"
            f"/providers/Microsoft.CognitiveServices/accounts"
            f"?api-version={ARM_API_VERSION}"
        )
        try:
            accounts = _arm_list(accounts_url, arm_token)
        except requests.HTTPError as error:
            if _status_code(error) == 404:
                return _fail(
                    f"Resource group nem található: '{resource_group}'."
                )
            return _fail(_http_message("AI Foundry lista sikertelen", error))

        matching_accounts = [
            account
            for account in accounts
            if account.get("kind") == "AIServices"
            and str(account.get("name", "")).startswith(foundry_spec["prefix"])
        ]
        if not matching_accounts:
            return _fail(
                f"Nem található AI Foundry, amely '{foundry_spec['prefix']}' "
                f"prefixszel kezdődik a resource groupban '{resource_group}'."
            )

        expected_project = foundry_spec["project"]
        projects = []
        for account in matching_accounts:
            account_name = account["name"]
            projects_url = (
                f"https://management.azure.com/subscriptions/{subscription_id}"
                f"/resourceGroups/{resource_group}"
                f"/providers/Microsoft.CognitiveServices/accounts/{account_name}"
                f"/projects?api-version={ARM_API_VERSION}"
            )
            try:
                account_projects = _arm_list(projects_url, arm_token)
            except requests.HTTPError as error:
                return _fail(
                    _http_message(
                        f"A(z) '{account_name}' Foundry projektjei nem kérdezhetők le",
                        error,
                    )
                )

            for project in account_projects:
                short_name = _project_name(project.get("name", ""))
                if short_name.lower() != expected_project.lower():
                    continue
                endpoint = (
                    (project.get("properties") or {})
                    .get("endpoints", {})
                    .get("AI Foundry API")
                )
                if not endpoint:
                    endpoint = (
                        f"https://{account_name}.services.ai.azure.com"
                        f"/api/projects/{short_name}"
                    )
                projects.append(
                    {
                        "account": account_name,
                        "name": short_name,
                        "endpoint": endpoint.rstrip("/"),
                    }
                )

        if not projects:
            foundry_names = ", ".join(account["name"] for account in matching_accounts)
            return _fail(
                f"A(z) '{expected_project}' projekt nem található ezekben a "
                f"Foundry erőforrásokban: {foundry_names}."
            )

        foundry_token = credential.get_token(FOUNDRY_SCOPE).token
        agent_prefix = foundry_spec["agent_prefix"]
        matching_agents = []
        for project in projects:
            try:
                agents = _list_agents(project["endpoint"], foundry_token)
            except requests.HTTPError as error:
                if _status_code(error) == 403:
                    return _fail(
                        f"Nincs jogosultság az ügynökök olvasásához a(z) "
                        f"'{project['account']}/{project['name']}' projektben. "
                        f"A hívó identitásnak Foundry User szerepkör kell "
                        f"az AI Foundry erőforráson."
                    )
                return _fail(
                    _http_message(
                        f"Az ügynökök lekérése sikertelen a(z) "
                        f"'{project['account']}/{project['name']}' projektben",
                        error,
                    )
                )

            for agent in agents:
                agent_name = agent.get("name") or agent.get("id") or ""
                if str(agent_name).startswith(agent_prefix):
                    matching_agents.append(f"{project['name']}/{agent_name}")

        if len(matching_agents) < foundry_spec["count"]:
            return _fail(
                f"Nem található elegendő ügynök, amely '{agent_prefix}' "
                f"prefixszel kezdődik a(z) '{expected_project}' projektben. "
                f"Elvárt: {foundry_spec['count']}, Talált: {len(matching_agents)}"
            )

        return {"success": True, "message": "Lab sikeresen ellenőrizve."}
    except Exception as error:
        return {"success": False, "message": str(error)}


def _arm_list(url: str, token: str) -> list[dict]:
    items = []
    headers = {"Authorization": f"Bearer {token}"}
    while url:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        payload = response.json()
        items.extend(payload.get("value") or [])
        url = payload.get("nextLink")
    return items


def _list_agents(endpoint: str, token: str) -> list[dict]:
    agents = []
    params = {"api-version": AGENTS_API_VERSION, "limit": 100}
    headers = {"Authorization": f"Bearer {token}"}
    while True:
        response = requests.get(
            f"{endpoint}/agents",
            headers=headers,
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        agents.extend(payload.get("data") or [])
        if not payload.get("has_more"):
            break
        last_id = payload.get("last_id")
        if not last_id:
            break
        params["after"] = last_id
    return agents


def _project_name(resource_name: str) -> str:
    return resource_name.rsplit("/", 1)[-1]


def _status_code(error: requests.HTTPError) -> int | None:
    if error.response is None:
        return None
    return error.response.status_code


def _http_message(prefix: str, error: requests.HTTPError) -> str:
    detail = ""
    if error.response is not None:
        try:
            body = error.response.json()
            detail = ((body.get("error") or {}).get("message")) or ""
        except ValueError:
            detail = (error.response.text or "")[:300]
    status = _status_code(error)
    if detail:
        return f"{prefix}. HTTP {status}. {detail}"
    return f"{prefix}. HTTP {status}."


def _fail(message: str) -> dict:
    return {"success": False, "message": message}
