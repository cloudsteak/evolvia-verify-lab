# Azure Functions — Evolvia Verify Lab

Azure-native verify service (Function App + APIM).

Mirrors the AWS layout: `lambda/` for AWS, `azure-function/` for Azure.

## Endpoints

| Route | Method | APIM path | Description |
|-------|--------|-----------|-------------|
| `health` | GET | `/health` | Health check |
| `dispatcher` | POST | `/v1/verify` | Lab verification router |

Supported labs: every directory under `checks/azure/` with a `verify.py` (e.g. `basic`, `mk-7-01-vm`, `mk-7-01-lb`, …). Routing uses dynamic import via `labs/registry.py`.

## Dependencies

**`pyproject.toml`** + **`uv.lock`**, `azure` extra:

```bash
uv sync --extra azure
```

There is **no committed `requirements.txt`**. `build.sh` exports deps from uv into the deploy zip; Azure **remote build** (`--build-remote`) installs them via Oryx on deploy.

## Local build (optional, debugging only)

Normal deploy is CD-only — do not run locally unless debugging packaging issues.

```bash
cd azure-function
chmod +x build.sh
./build.sh
# → release.zip
```

## CI / CD

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `azure-functions-ci.yml` | Pull request | Ruff lint + pytest (`uv sync --extra azure`) |
| `azure-functions-deploy.yml` | Push to `main` | Build, deploy, APIM key sync, smoke test |

Full setup (infra, secrets, backend config): [evolvia-foundation/azure/README.md](https://github.com/cloudsteak/evolvia-foundation/blob/main/azure/README.md)

Deploy is fully automated: push to `main` runs build, zip deploy, APIM function-key sync, and `/health` smoke test. No local scripts required.

### GitHub secrets (CD)

Set in this repo → Settings → Secrets (from `evolvia-foundation/azure/12-oidc` apply):

| Secret | Source |
|--------|--------|
| `AZURE_DEPLOY_CLIENT_ID` | `tofu output` → `github_actions_client_ids["evolvia-verify-lab"]` |
| `AZURE_DEPLOY_TENANT_ID` | `tofu output tenant_id` |
| `AZURE_DEPLOY_SUBSCRIPTION_ID` | `tofu output subscription_id` |

### GitHub variables (CD, required)

Set in this repo → Settings → Secrets and variables → Actions → **Variables** (from `evolvia-foundation/azure/50-verify` outputs):

```bash
cd evolvia-foundation/azure/50-verify
tofu output -raw resource_group_name
tofu output -raw function_app_name
tofu output -raw apim_name
tofu output -raw health_check_url
```

If `apim_name` fails, run `tofu apply` in `50-verify` first.

| Variable | Output |
|----------|--------|
| `AZURE_VERIFY_RESOURCE_GROUP` | `resource_group_name` |
| `AZURE_VERIFY_FUNCTION_APP` | `function_app_name` |
| `AZURE_VERIFY_APIM_NAME` | `apim_name` |
| `AZURE_VERIFY_HEALTH_CHECK_URL` | `health_check_url` |

The deploy workflow has **no in-repo defaults** for these names.

## Manual deploy

Not needed for normal use — CD on push to `main` handles build, deploy, APIM key sync, and smoke test.

Fallback only:

```bash
cd azure-function && ./build.sh

RG=$(cd ../evolvia-foundation/azure/50-verify && tofu output -raw resource_group_name)
APP=$(cd ../evolvia-foundation/azure/50-verify && tofu output -raw function_app_name)

az functionapp deployment source config-zip \
  --resource-group "$RG" \
  --name "$APP" \
  --src release.zip
```

## Environment variables (Function App)

| Variable | Description |
|----------|-------------|
| `AZURE_SUBSCRIPTION_ID` | Lab subscription to verify |
| `LOG_LEVEL` | Optional, default `INFO` |

Authentication to Azure Resource Manager uses **Managed Identity** (`DefaultAzureCredential`).
