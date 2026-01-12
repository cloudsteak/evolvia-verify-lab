# Evolvia Verify Lab

Lab verification microservice for CloudMentor.

## API

### Health Check
```
GET /health
```

### Verify Lab
```
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

| Variable | Required | Description |
|----------|----------|-------------|
| AZURE_SUBSCRIPTION_ID | Yes | Azure subscription ID |
| AZURE_TENANT_ID | Yes | Azure tenant ID |
| AZURE_CLIENT_ID | Yes | Service Principal client ID |
| AZURE_CLIENT_SECRET | Yes | Service Principal client secret |
| INTERNAL_VERIFY_API_KEY | No | API key for authentication |

## Local Development
```bash
uv sync
uv run uvicorn main:app --reload
```

## Docker
```bash
docker build -t evolvia-verify-lab .
docker run -p 8000:8000 --env-file .env evolvia-verify-lab
```
