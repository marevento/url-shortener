"""
Unit tests for URL Shortener Lambda handler.
Uses moto to mock DynamoDB.
"""

import json
import os
import sys

import boto3
import pytest
from moto import mock_aws

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Set environment variable before importing handler
os.environ["DYNAMODB_TABLE"] = "url-shortener-test"
os.environ.setdefault("BASE_URL", "https://example.short.url")


@pytest.fixture
def aws_credentials():
    """Mock AWS credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


@pytest.fixture
def dynamodb_table(aws_credentials):
    """Create a mock DynamoDB table."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
            TableName="url-shortener-test",
            KeySchema=[{"AttributeName": "short_code", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "short_code", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()

        # Reimport handler to use mocked DynamoDB
        import importlib
        import handler

        importlib.reload(handler)

        yield table


@pytest.fixture
def sample_url_item():
    """Sample URL item for testing."""
    return {
        "short_code": "abc123",
        "original_url": "https://example.com/long/url/path",
        "created_at": "2024-01-15T10:30:00+00:00",
        "clicks": 0,
    }


class TestCreateShortUrl:
    """Tests for the create_short_url function."""

    def test_create_short_url_success(self, dynamodb_table):
        """Test successful short URL creation."""
        import handler

        event = {
            "body": json.dumps({"url": "https://example.com/test"}),
            "headers": {"Host": "api.example.com"},
            "requestContext": {"stage": "$default"},
        }

        response = handler.create_short_url(event, None)

        assert response["statusCode"] == 201
        body = json.loads(response["body"])
        assert "short_url" in body
        assert "short_code" in body
        assert len(body["short_code"]) == 6

    def test_create_short_url_missing_url(self, dynamodb_table):
        """Test error when URL is missing."""
        import handler

        event = {"body": json.dumps({}), "headers": {}, "requestContext": {}}

        response = handler.create_short_url(event, None)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "error" in body
        assert "url" in body["error"].lower()

    def test_create_short_url_invalid_url(self, dynamodb_table):
        """Test error when URL is invalid."""
        import handler

        event = {
            "body": json.dumps({"url": "not-a-valid-url"}),
            "headers": {},
            "requestContext": {},
        }

        response = handler.create_short_url(event, None)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "error" in body
        assert "invalid" in body["error"].lower()

    def test_create_short_url_invalid_json(self, dynamodb_table):
        """Test error when body is invalid JSON."""
        import handler

        event = {"body": "not json", "headers": {}, "requestContext": {}}

        response = handler.create_short_url(event, None)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "error" in body

    def test_create_short_url_custom_code(self, dynamodb_table):
        """Test creating a short URL with a custom slug."""
        import handler

        event = {
            "body": json.dumps({"url": "https://example.com/test", "code": "my-slug"}),
            "headers": {},
            "requestContext": {},
        }

        response = handler.create_short_url(event, None)

        assert response["statusCode"] == 201
        body = json.loads(response["body"])
        assert body["short_code"] == "my-slug"
        assert "my-slug" in body["short_url"]

    def test_create_short_url_custom_code_conflict(self, dynamodb_table):
        """Test 409 when custom slug already exists."""
        import handler

        dynamodb_table.put_item(
            Item={
                "short_code": "taken",
                "original_url": "https://example.com/existing",
                "created_at": "2024-01-01T00:00:00+00:00",
                "clicks": 0,
            }
        )

        event = {
            "body": json.dumps({"url": "https://example.com/new", "code": "taken"}),
            "headers": {},
            "requestContext": {},
        }

        response = handler.create_short_url(event, None)

        assert response["statusCode"] == 409
        body = json.loads(response["body"])
        assert "already taken" in body["error"].lower()

    def test_create_short_url_custom_code_invalid(self, dynamodb_table):
        """Test 400 when custom slug has invalid format."""
        import handler

        invalid_codes = ["-starts-with-hyphen", "has spaces", "a" * 65, "special!chars"]
        for code in invalid_codes:
            event = {
                "body": json.dumps({"url": "https://example.com/test", "code": code}),
                "headers": {},
                "requestContext": {},
            }

            response = handler.create_short_url(event, None)
            assert response["statusCode"] == 400, f"Expected 400 for code: {code}"


class TestApiKeyAuth:
    """Tests for API key authentication on POST /shorten."""

    def test_rejects_request_without_api_key(self, dynamodb_table):
        """Test 403 when API key is required but not provided."""
        import handler

        original_key = handler.API_KEY
        handler.API_KEY = "test-secret-key"
        try:
            event = {
                "body": json.dumps({"url": "https://example.com/test"}),
                "headers": {},
                "requestContext": {},
            }

            response = handler.create_short_url(event, None)
            assert response["statusCode"] == 403
        finally:
            handler.API_KEY = original_key

    def test_rejects_request_with_wrong_api_key(self, dynamodb_table):
        """Test 403 when API key is wrong."""
        import handler

        original_key = handler.API_KEY
        handler.API_KEY = "test-secret-key"
        try:
            event = {
                "body": json.dumps({"url": "https://example.com/test"}),
                "headers": {"x-api-key": "wrong-key"},
                "requestContext": {},
            }

            response = handler.create_short_url(event, None)
            assert response["statusCode"] == 403
        finally:
            handler.API_KEY = original_key

    def test_accepts_request_with_correct_api_key(self, dynamodb_table):
        """Test success when correct API key is provided."""
        import handler

        original_key = handler.API_KEY
        handler.API_KEY = "test-secret-key"
        try:
            event = {
                "body": json.dumps({"url": "https://example.com/test"}),
                "headers": {"x-api-key": "test-secret-key"},
                "requestContext": {},
            }

            response = handler.create_short_url(event, None)
            assert response["statusCode"] == 201
        finally:
            handler.API_KEY = original_key

    def test_no_auth_when_api_key_not_configured(self, dynamodb_table):
        """Test that auth is skipped when API_KEY env var is empty."""
        import handler

        original_key = handler.API_KEY
        handler.API_KEY = ""
        try:
            event = {
                "body": json.dumps({"url": "https://example.com/test"}),
                "headers": {},
                "requestContext": {},
            }

            response = handler.create_short_url(event, None)
            assert response["statusCode"] == 201
        finally:
            handler.API_KEY = original_key


class TestRedirect:
    """Tests for the redirect function."""

    def test_redirect_success(self, dynamodb_table, sample_url_item):
        """Test successful redirect."""
        import handler

        # Insert test item
        dynamodb_table.put_item(Item=sample_url_item)

        event = {"pathParameters": {"code": "abc123"}}

        response = handler.redirect(event, None)

        assert response["statusCode"] == 301
        assert response["headers"]["Location"] == sample_url_item["original_url"]

    def test_redirect_increments_clicks(self, dynamodb_table, sample_url_item):
        """Test that redirect increments click counter."""
        import handler

        dynamodb_table.put_item(Item=sample_url_item)

        event = {"pathParameters": {"code": "abc123"}}

        # Call redirect multiple times
        handler.redirect(event, None)
        handler.redirect(event, None)
        handler.redirect(event, None)

        # Verify click count
        result = dynamodb_table.get_item(Key={"short_code": "abc123"})
        assert result["Item"]["clicks"] == 3

    def test_redirect_not_found(self, dynamodb_table):
        """Test 404 when short code doesn't exist."""
        import handler

        event = {"pathParameters": {"code": "nonexistent"}}

        response = handler.redirect(event, None)

        assert response["statusCode"] == 404
        body = json.loads(response["body"])
        assert "error" in body

    def test_redirect_missing_code(self, dynamodb_table):
        """Test error when code is missing."""
        import handler

        event = {"pathParameters": {}}

        response = handler.redirect(event, None)

        assert response["statusCode"] == 400


class TestGetStats:
    """Tests for the get_stats function."""

    def test_get_stats_success(self, dynamodb_table, sample_url_item):
        """Test successful stats retrieval."""
        import handler

        sample_url_item["clicks"] = 42
        dynamodb_table.put_item(Item=sample_url_item)

        event = {"pathParameters": {"code": "abc123"}}

        response = handler.get_stats(event, None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["short_code"] == "abc123"
        assert body["original_url"] == sample_url_item["original_url"]
        assert body["clicks"] == 42
        assert "created_at" in body

    def test_get_stats_not_found(self, dynamodb_table):
        """Test 404 when short code doesn't exist."""
        import handler

        event = {"pathParameters": {"code": "nonexistent"}}

        response = handler.get_stats(event, None)

        assert response["statusCode"] == 404

    def test_get_stats_missing_code(self, dynamodb_table):
        """Test error when code is missing."""
        import handler

        event = {"pathParameters": {}}

        response = handler.get_stats(event, None)

        assert response["statusCode"] == 400


class TestHandler:
    """Tests for the main handler routing."""

    def test_handler_routes_to_create(self, dynamodb_table):
        """Test that POST /shorten routes correctly."""
        import handler

        event = {
            "requestContext": {"http": {"method": "POST"}},
            "rawPath": "/shorten",
            "body": json.dumps({"url": "https://example.com"}),
            "headers": {"Host": "api.example.com"},
        }

        response = handler.handler(event, None)
        assert response["statusCode"] == 201

    def test_handler_routes_to_stats(self, dynamodb_table, sample_url_item):
        """Test that GET /stats/{code} routes correctly."""
        import handler

        dynamodb_table.put_item(Item=sample_url_item)

        event = {
            "requestContext": {"http": {"method": "GET"}},
            "rawPath": "/stats/abc123",
            "pathParameters": {"code": "abc123"},
        }

        response = handler.handler(event, None)
        assert response["statusCode"] == 200

    def test_handler_routes_to_redirect(self, dynamodb_table, sample_url_item):
        """Test that GET /{code} routes correctly."""
        import handler

        dynamodb_table.put_item(Item=sample_url_item)

        event = {
            "requestContext": {"http": {"method": "GET"}},
            "rawPath": "/abc123",
            "pathParameters": {"code": "abc123"},
        }

        response = handler.handler(event, None)
        assert response["statusCode"] == 301

    def test_handler_returns_404_for_unknown_route(self, dynamodb_table):
        """Test 404 for unknown routes."""
        import handler

        event = {
            "requestContext": {"http": {"method": "DELETE"}},
            "rawPath": "/unknown",
            "pathParameters": {},
        }

        response = handler.handler(event, None)
        assert response["statusCode"] == 404


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_generate_short_code_length(self):
        """Test that generated codes have correct length."""
        import handler

        code = handler.generate_short_code(6)
        assert len(code) == 6

        code = handler.generate_short_code(10)
        assert len(code) == 10

    def test_generate_short_code_characters(self):
        """Test that generated codes only contain base62 characters."""
        import handler

        for _ in range(100):
            code = handler.generate_short_code()
            assert all(c in handler.BASE62_CHARS for c in code)

    def test_is_valid_url(self):
        """Test URL validation."""
        import handler

        # Valid URLs
        assert handler.is_valid_url("https://example.com")
        assert handler.is_valid_url("http://example.com/path")
        assert handler.is_valid_url("https://example.com/path?query=1")

        # Invalid URLs
        assert not handler.is_valid_url("not-a-url")
        assert not handler.is_valid_url("ftp://example.com")
        assert not handler.is_valid_url("")
        assert not handler.is_valid_url("example.com")
