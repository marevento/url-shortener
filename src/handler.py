"""
URL Shortener Lambda Handler

Provides endpoints for creating short URLs, redirecting, and retrieving statistics.
"""

import json
import os
import re
import string
import secrets
from datetime import datetime, timezone
from urllib.parse import urlparse

import boto3
from botocore.exceptions import ClientError

# Initialize DynamoDB resource
dynamodb = boto3.resource("dynamodb")
TABLE_NAME = os.environ.get("DYNAMODB_TABLE", "url-shortener")
BASE_URL = os.environ.get("BASE_URL", "")
CORS_ORIGIN = os.environ.get("CORS_ORIGIN", BASE_URL)
API_KEY = os.environ.get("API_KEY", "")
table = dynamodb.Table(TABLE_NAME)

# Base62 characters for short code generation
BASE62_CHARS = string.ascii_letters + string.digits
CUSTOM_CODE_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9\-]{0,63}$")


def generate_short_code(length: int = 6) -> str:
    """Generate a random base62 short code."""
    return "".join(secrets.choice(BASE62_CHARS) for _ in range(length))


def is_valid_url(url: str) -> bool:
    """Validate that the URL has a valid scheme and netloc."""
    try:
        result = urlparse(url)
        return all([result.scheme in ("http", "https"), result.netloc])
    except ValueError:
        return False


def json_response(status_code: int, body: dict) -> dict:
    """Create a standard JSON response."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": CORS_ORIGIN,
        },
        "body": json.dumps(body),
    }


def redirect_response(url: str) -> dict:
    """Create a 301 redirect response."""
    return {
        "statusCode": 301,
        "headers": {
            "Location": url,
            "Cache-Control": "no-cache",
        },
        "body": "",
    }


def create_short_url(event: dict, context) -> dict:
    """
    POST /shorten
    Create a new short URL.

    Request body: {"url": "https://example.com/long/url", "code": "optional-custom-slug"}
    Response: {"short_url": "https://<domain>/abc123", "short_code": "abc123"}
    """
    if API_KEY:
        request_key = event.get("headers", {}).get("x-api-key", "")
        if not secrets.compare_digest(request_key, API_KEY):
            return json_response(403, {"error": "Forbidden"})

    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return json_response(400, {"error": "Invalid JSON body"})

    original_url = body.get("url")
    if not original_url:
        return json_response(400, {"error": "Missing 'url' field"})

    if len(original_url) > 2048:
        return json_response(400, {"error": "URL too long (max 2048 characters)"})

    if not is_valid_url(original_url):
        return json_response(400, {"error": "Invalid URL format"})

    if not BASE_URL:
        return json_response(500, {"error": "Server misconfiguration"})

    custom_code = body.get("code")
    if custom_code:
        if not CUSTOM_CODE_RE.match(custom_code):
            return json_response(400, {"error": "Invalid code format (use a-z, 0-9, hyphens, 1-64 chars)"})
        try:
            table.put_item(
                Item={
                    "short_code": custom_code,
                    "original_url": original_url,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "clicks": 0,
                },
                ConditionExpression="attribute_not_exists(short_code)",
            )
            short_code = custom_code
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return json_response(409, {"error": "Code already taken"})
            raise
    else:
        # Generate unique short code with collision handling
        max_attempts = 5
        for _ in range(max_attempts):
            short_code = generate_short_code()
            try:
                table.put_item(
                    Item={
                        "short_code": short_code,
                        "original_url": original_url,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "clicks": 0,
                    },
                    ConditionExpression="attribute_not_exists(short_code)",
                )
                break
            except ClientError as e:
                if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                    continue
                raise
        else:
            return json_response(500, {"error": "Failed to generate unique short code"})

    return json_response(
        201,
        {
            "short_url": f"{BASE_URL}/{short_code}",
            "short_code": short_code,
        },
    )


def redirect(event: dict, context) -> dict:
    """
    GET /{code}
    Redirect to the original URL and increment click counter.
    """
    short_code = event.get("pathParameters", {}).get("code")
    if not short_code:
        return json_response(400, {"error": "Missing short code"})

    # Get the item and increment clicks atomically
    try:
        response = table.update_item(
            Key={"short_code": short_code},
            UpdateExpression="SET clicks = if_not_exists(clicks, :zero) + :inc",
            ExpressionAttributeValues={":inc": 1, ":zero": 0},
            ConditionExpression="attribute_exists(short_code)",
            ReturnValues="ALL_NEW",
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return json_response(404, {"error": "Short URL not found"})
        raise

    original_url = response["Attributes"]["original_url"]
    if not is_valid_url(original_url):
        return json_response(502, {"error": "Stored URL is invalid"})
    return redirect_response(original_url)


def get_stats(event: dict, context) -> dict:
    """
    GET /stats/{code}
    Get statistics for a short URL.
    """
    short_code = event.get("pathParameters", {}).get("code")
    if not short_code:
        return json_response(400, {"error": "Missing short code"})

    response = table.get_item(Key={"short_code": short_code})
    item = response.get("Item")

    if not item:
        return json_response(404, {"error": "Short URL not found"})

    return json_response(
        200,
        {
            "short_code": item["short_code"],
            "original_url": item["original_url"],
            "clicks": int(item.get("clicks", 0)),
            "created_at": item["created_at"],
        },
    )


def handler(event: dict, context) -> dict:
    """
    Main Lambda handler - routes requests to appropriate function.
    """
    http_method = event.get("requestContext", {}).get("http", {}).get("method")
    path = event.get("rawPath", "")

    # Handle API Gateway v1 format as well
    if not http_method:
        http_method = event.get("httpMethod")
        path = event.get("path", "")

    if http_method == "POST" and path.endswith("/shorten"):
        return create_short_url(event, context)
    elif http_method == "GET" and "/stats/" in path:
        return get_stats(event, context)
    elif http_method == "GET" and event.get("pathParameters", {}).get("code"):
        return redirect(event, context)
    else:
        return json_response(404, {"error": "Not found"})
