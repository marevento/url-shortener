# URL Shortener

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![Terraform](https://img.shields.io/badge/terraform-%3E%3D1.0-purple.svg)](https://www.terraform.io/)
[![AWS Lambda](https://img.shields.io/badge/deployed-AWS%20Lambda-orange.svg)](https://aws.amazon.com/lambda/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A serverless URL shortener built with AWS Lambda, DynamoDB, and Terraform.

**Live demo available** — deployed with a custom domain via Route 53 subdomain delegation.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/shorten` | Create short URL |
| GET | `/{code}` | Redirect to original URL |
| GET | `/stats/{code}` | Get click statistics |

## Prerequisites

- AWS CLI configured with appropriate credentials
- Terraform >= 1.0
- Python 3.12
- A domain with DNS management at your registrar (for subdomain delegation)

## Deployment

### Step 1: Initial deploy (creates Route 53 hosted zone)

```bash
cd infra
terraform init
terraform apply -target=aws_route53_zone.subdomain
```

This outputs 4 nameservers.

### Step 2: Configure your domain registrar DNS

At your domain registrar, add NS records for the `go` subdomain:
```
go  NS  ns-xxx.awsdns-xx.org.
go  NS  ns-xxx.awsdns-xx.co.uk.
go  NS  ns-xxx.awsdns-xx.com.
go  NS  ns-xxx.awsdns-xx.net.
```

Wait for DNS propagation (check with `dig <your-subdomain> NS`).

### Step 3: Complete deployment

```bash
terraform apply
```

This creates the ACM certificate, validates it, and sets up the API Gateway custom domain.

## Usage

### Create a short URL

```bash
curl -X POST https://<your-domain>/shorten \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/very/long/url"}'
```

Response:
```json
{
  "short_url": "https://<your-domain>/abc123",
  "short_code": "abc123"
}
```

### Access short URL

Navigate to `https://<your-domain>/abc123` - you'll be redirected to the original URL.

### Get statistics

```bash
curl https://<your-domain>/stats/abc123
```

Response:
```json
{
  "short_code": "abc123",
  "original_url": "https://example.com/very/long/url",
  "clicks": 42,
  "created_at": "2024-01-15T10:30:00Z"
}
```

## Testing

```bash
pip install -r requirements-dev.txt
pytest tests/
```

## Project Structure

```
url-shortener/
├── infra/
│   ├── main.tf           # Lambda, DynamoDB, API Gateway, IAM, Route 53
│   ├── variables.tf
│   └── outputs.tf
├── src/
│   └── handler.py        # Lambda function code
├── tests/
│   └── test_handler.py   # Unit tests
└── README.md
```
