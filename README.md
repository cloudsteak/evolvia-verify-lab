# Evolvia Verify Lab

Lab verification microservice for CloudMentor.

## Multi-Provider Architecture

One codebase produces three provider-specific Docker images:

- `azure`: installs only Azure SDK dependencies
- `aws`: installs only AWS SDK dependencies
- `gcp`: installs only GCP SDK dependencies

The active provider is controlled by `PROVIDER`. The service exposes the same `POST /v1/verify` API contract for every image, while `GET /info` reports the active provider and service version.

## API

### Health Check

```http
GET /health
```

### Service Info

```http
GET /info
```

Example response:

```json
{
  "provider": "azure",
  "version": "0.1.1"
}
```

### Verify Lab

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

## Environment Variables

### Common

| Variable | Required | Description |
|----------|----------|-------------|
| `PROVIDER` | Yes | Active provider: `azure`, `aws`, or `gcp` |
| `INTERNAL_VERIFY_API_KEY` | No | Legacy common API key for authentication |
| `INTERNAL_VERIFY_AZURE_API_KEY` | No | Azure verify API key; falls back to the common key |
| `INTERNAL_VERIFY_AWS_API_KEY` | No | AWS verify API key; falls back to the common key |
| `INTERNAL_VERIFY_GCP_API_KEY` | No | GCP verify API key; falls back to the common key |

### Azure

| Variable | Required When | Description |
|----------|---------------|-------------|
| `AZURE_SUBSCRIPTION_ID` | `PROVIDER=azure` | Azure subscription ID |
| `AZURE_TENANT_ID` | `PROVIDER=azure` | Azure tenant ID |
| `AZURE_CLIENT_ID` | `PROVIDER=azure` | Service Principal client ID |
| `AZURE_CLIENT_SECRET` | `PROVIDER=azure` | Service Principal client secret |

### AWS

| Variable | Required When | Description |
|----------|---------------|-------------|
| `AWS_REGION` | `PROVIDER=aws` | AWS region for EC2 and VPC checks |
| `AWS_ACCOUNT_ID` | `PROVIDER=aws` | Expected AWS account ID |

Available AWS labs:

- `basic`
- `ec2-website`
- `s3-static-website`
- `rds-mysql`

### GCP

| Variable | Required When | Description |
|----------|---------------|-------------|
| `GCP_PROJECT_ID` | `PROVIDER=gcp` | GCP project ID for Compute Engine and VPC checks |

## Local Development

Azure example:

```bash
uv sync --extra azure
uv run uvicorn main:app --reload
```

AWS example:

```bash
uv sync --extra aws
PROVIDER=aws uv run uvicorn main:app --reload
```

GCP example:

```bash
uv sync --extra gcp
PROVIDER=gcp uv run uvicorn main:app --reload
```

## Docker

Azure image:

```bash
docker build --build-arg PROVIDER=azure -t evolvia-verify-lab-azure .
docker run -p 8000:8000 --env-file .env evolvia-verify-lab-azure
```

AWS image:

```bash
docker build --build-arg PROVIDER=aws -t evolvia-verify-lab-aws .
docker run -p 8000:8000 --env-file .env evolvia-verify-lab-aws
```

GCP image:

```bash
docker build --build-arg PROVIDER=gcp -t evolvia-verify-lab-gcp .
docker run -p 8000:8000 --env-file .env evolvia-verify-lab-gcp
```
