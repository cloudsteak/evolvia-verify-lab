# Evolvia Verify Lab

Lab verification service for CloudMentor. Each cloud provider has its own serverless deployment path:

| Cloud | Runtime | Code | Deploy |
|-------|---------|------|--------|
| Azure | Function App + APIM | `azure-function/` | `azure-functions-deploy.yml` |
| AWS | Lambda + API Gateway | `lambda/` | `lambda-deploy.yml` |

Shared lab logic lives under `checks/`:

- `checks/azure/` — Azure lab handlers (`verify.py` + `lab_spec.json`), packaged into the Function App zip
- `checks/aws/` — `lab_spec.json` only; bundled into Lambda zips at deploy time

## API contract

All entry points expose the same verify contract:

```http
POST /v1/verify
Header: X-API-Key: <secret>
Content-Type: application/json

{
  "user": "student123",
  "email": "student@example.com",
  "cloud": "azure",
  "lab": "basic"
}
```

Azure also exposes `GET /health` on APIM (`/health`).

## Azure Functions

Production Azure verify runs on APIM + Function App — not Kubernetes.

See [azure-function/README.md](azure-function/README.md) for build, deploy, and GitHub secrets/variables.

Infra setup: [evolvia-foundation/azure/README.md](https://github.com/cloudsteak/evolvia-foundation/blob/main/azure/README.md)

Local CI:

```bash
uv sync --frozen --extra azure --group dev
uv run ruff check azure-function/ checks/azure/
uv run pytest azure-function/tests/ -q
```

## AWS Lambda

Production AWS verify runs on API Gateway + Lambda.

Lab handlers live in `lambda/aws/`. The deploy workflow copies `checks/aws/<lab>/lab_spec.json` into each function zip.

Available AWS labs:

- `basic`
- `ec2-website`
- `s3-static-website`
- `rds-mysql`

Infra setup: [evolvia-foundation/aws/50-verify](https://github.com/cloudsteak/evolvia-foundation/tree/main/aws/50-verify)
