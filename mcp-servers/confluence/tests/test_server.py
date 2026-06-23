from __future__ import annotations

import os
import sys
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("CONFLUENCE_CLIENT_ID", "test-client-id")
os.environ.setdefault("CONFLUENCE_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("CONFLUENCE_TOKEN", "test-bearer-token")


@pytest.fixture(autouse=True)
def mock_client_cls():
    with patch("server.ConfluenceClient") as mock_cls:
        client = MagicMock()
        mock_cls.return_value = client
        yield client


# ── confluence_test_connection ───────────────────────────────────────────────

def test_test_connection_success(mock_client_cls):
    from server import confluence_test_connection
    mock_client_cls.get.return_value = {
        "results": [{"name": "VCC Operations"}],
        "size": 1,
    }
    result = confluence_test_connection()
    assert "✅" in result
    assert "VCC Operations" in result
    mock_client_cls.get.assert_called_once_with("rest/api/space", params={"limit": 1})


def test_test_connection_error(mock_client_cls):
    from server import confluence_test_connection
    mock_client_cls.get.return_value = "❌ Auth failed — check CONFLUENCE_TOKEN"
    result = confluence_test_connection()
    assert result == "❌ Auth failed — check CONFLUENCE_TOKEN"


# ── confluence_search ────────────────────────────────────────────────────────

def test_search_returns_results(mock_client_cls):
    from server import confluence_search
    mock_client_cls.get.return_value = {
        "results": [
            {
                "id": "9967739",
                "title": "Clear a Stuck Call",
                "space": {"key": "VCCOPS", "name": "VCC Operations"},
                "excerpt": "<p>This page describes how to clear a stuck call.</p>",
            }
        ],
        "totalSize": 1,
    }
    result = confluence_search("stuck call")
    assert "Clear a Stuck Call" in result
    assert "VCCOPS" in result
    assert "https://confluence.8x8.com/pages/9967739" in result
    assert "stuck call" in result.lower() or "Clear" in result


def test_search_empty_results(mock_client_cls):
    from server import confluence_search
    mock_client_cls.get.return_value = {"results": [], "totalSize": 0}
    result = confluence_search("xyzzy nonexistent")
    assert "⚠️" in result
    assert "xyzzy nonexistent" in result


def test_search_error_passthrough(mock_client_cls):
    from server import confluence_search
    mock_client_cls.get.return_value = "❌ CF-Access rejected — check CONFLUENCE_CLIENT_ID/SECRET"
    result = confluence_search("runbook")
    assert result == "❌ CF-Access rejected — check CONFLUENCE_CLIENT_ID/SECRET"


def test_search_passes_cql_and_limit(mock_client_cls):
    from server import confluence_search
    mock_client_cls.get.return_value = {"results": [], "totalSize": 0}
    confluence_search("stuck call", limit=5)
    call_params = mock_client_cls.get.call_args[1]["params"]
    assert "stuck call" in call_params["cql"]
    assert call_params["limit"] == 5


# ── confluence_get_page ──────────────────────────────────────────────────────

def test_get_page_returns_markdown(mock_client_cls):
    from server import confluence_get_page
    mock_client_cls.get.return_value = {
        "id": "9967739",
        "title": "Clear a Stuck Call",
        "space": {"key": "VCCOPS"},
        "version": {
            "when": "2026-01-15T10:00:00.000Z",
            "by": {"displayName": "Jane Doe"},
        },
        "body": {
            "storage": {
                "value": "<h2>Steps</h2><p>Step 1: Restart the service.</p>"
            }
        },
    }
    result = confluence_get_page("9967739")
    assert "Clear a Stuck Call" in result
    assert "VCCOPS" in result
    assert "Jane Doe" in result
    assert "https://confluence.8x8.com/pages/9967739" in result
    assert "Steps" in result
    assert "Restart the service" in result


def test_get_page_error_passthrough(mock_client_cls):
    from server import confluence_get_page
    mock_client_cls.get.return_value = "❌ Page not found: rest/api/content/9999999"
    result = confluence_get_page("9999999")
    assert result == "❌ Page not found: rest/api/content/9999999"


def test_get_page_calls_correct_endpoint(mock_client_cls):
    from server import confluence_get_page
    mock_client_cls.get.return_value = "❌ Page not found: rest/api/content/1234"
    confluence_get_page("1234")
    called_endpoint = mock_client_cls.get.call_args[0][0]
    assert "1234" in called_endpoint
    called_params = mock_client_cls.get.call_args[1]["params"]
    assert "body.storage" in called_params["expand"]
