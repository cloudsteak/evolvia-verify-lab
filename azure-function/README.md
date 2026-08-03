# Azure Functions — Evolvia Verify Lab

Azure-native verify service for the `evolvia-verify-azure` Function App.

Mirrors the AWS layout: `lambda/` for AWS, `azure-function/` for Azure.

## Endpoints

| Route | Method | APIM path | Description |
|-------|--------|-----------|-------------|
| `health` | GET | `/health` | Health check |
| `dispatcher` | POST | `/v1/verify` | Lab verification router |

Supported labs: `basic` (more can be registered in `labs/registry.py`).

## Dependencies

Same as the Docker image — **`pyproject.toml`** + **`uv.lock`**, `azure` extra:

```bash
uv sync --extra azure
```

There is **no committed `requirements.txt`**. `build.sh` exports deps from uv at build time and bundles them into `.python_packages/` inside the zip.

## Local build

```bash
cd azure-function
chmod +x build.sh
./build.sh
# → release.zip
```

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12.

## CI / CD

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `azure-functions-ci.yml` | Pull request | Ruff lint + pytest (`uv sync --extra azure`) |
| `azure-functions-deploy.yml` | Push to `main` | Build zip + deploy Function App |

Full setup (infra, secrets, APIM function-key, backend config, smoke tests):
[evolvia-foundation/azure/README.md](https://github.com/cloudsteak/evolvia-foundation/blob/main/azure/README.md)

### GitHub secrets (CD)

Set in this repo → Settings → Secrets (from `evolvia-foundation/azure/12-oidc` apply):

| Secret | Source |
|--------|--------|
| `AZURE_DEPLOY_CLIENT_ID` | `tofu output` → `github_actions_client_ids["evolvia-verify-lab"]` |
| `AZURE_DEPLOY_TENANT_ID` | `tofu output tenant_id` |
| `AZURE_DEPLOY_SUBSCRIPTION_ID` | `tofu output subscription_id` |

## Manual deploy

```bash
cd azure-function && ./build.sh

az functionapp deployment source config-zip \
  --resource-group evolvia-verify-rg \
  --name evolvia-verify-azure \
  --src azure-function/release.zip
```

After deploy, update the APIM `function-key` named value with the Function App host key:

```bash
az functionapp keys list -g evolvia-verify-rg -n evolvia-verify-azure \
  --query "functionKeys.default" -o tsv
```

## Environment variables (Function App)

| Variable | Description |
|----------|-------------|
| `AZURE_SUBSCRIPTION_ID` | Lab subscription to verify |
| `LOG_LEVEL` | Optional, default `INFO` |

Authentication to Azure Resource Manager uses **Managed Identity** (`DefaultAzureCredential`).
