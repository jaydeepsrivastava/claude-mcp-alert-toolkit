from __future__ import annotations

import os
import sys
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("CHECKMK_BASE_URL", "http://fake/api/1.0")
os.environ.setdefault("CHECKMK_TOKEN", "automation test-token-1234")


@pytest.fixture(autouse=True)
def mock_client_cls():
    """Patch CheckMKClient at the server module level for every test."""
    with patch("server.CheckMKClient") as mock_cls:
        client = MagicMock()
        mock_cls.return_value = client
        yield client


# ── checkmk_test_connection ──────────────────────────────────────────────────

def test_test_connection_success(mock_client_cls):
    from server import checkmk_test_connection
    mock_client_cls.get.return_value = {"versions": {"checkmk": "2.2.0p11.cee"}}
    result = checkmk_test_connection()
    assert "✅" in result
    assert "2.2.0p11.cee" in result
    mock_client_cls.get.assert_called_once_with("version")


def test_test_connection_error(mock_client_cls):
    from server import checkmk_test_connection
    mock_client_cls.get.return_value = "❌ Connection failed: refused"
    result = checkmk_test_connection()
    assert result == "❌ Connection failed: refused"


# ── checkmk_list_problems ────────────────────────────────────────────────────

def test_list_problems_returns_problems(mock_client_cls):
    from server import checkmk_list_problems
    mock_client_cls.get.return_value = {
        "value": [
            {"extensions": {"host_name": "us1app001", "display_name": "CPU load", "state": 2, "plugin_output": "CRIT - load 90%"}},
            {"extensions": {"host_name": "us1app002", "display_name": "Disk /", "state": 1, "plugin_output": "WARN - 85% used"}},
        ]
    }
    result = checkmk_list_problems()
    assert "2 problem" in result
    assert "[CRIT] us1app001" in result
    assert "[WARN] us1app002" in result


def test_list_problems_empty(mock_client_cls):
    from server import checkmk_list_problems
    mock_client_cls.get.return_value = {"value": []}
    result = checkmk_list_problems()
    assert "No WARN/CRIT" in result


def test_list_problems_propagates_error(mock_client_cls):
    from server import checkmk_list_problems
    mock_client_cls.get.return_value = "❌ Auth failed — check CHECKMK_TOKEN"
    result = checkmk_list_problems()
    assert result == "❌ Auth failed — check CHECKMK_TOKEN"


# ── checkmk_get_host_status ──────────────────────────────────────────────────

def test_get_host_status_up(mock_client_cls):
    from server import checkmk_get_host_status
    mock_client_cls.get.return_value = {
        "value": [{"extensions": {"state": 0, "address": "10.0.0.1", "plugin_output": "Ping OK"}}]
    }
    result = checkmk_get_host_status("us1app001")
    assert "UP" in result
    assert "us1app001" in result


def test_get_host_status_down(mock_client_cls):
    from server import checkmk_get_host_status
    mock_client_cls.get.return_value = {
        "value": [{"extensions": {"state": 1, "address": "10.0.0.2", "plugin_output": "Ping failed"}}]
    }
    result = checkmk_get_host_status("us1app002")
    assert "DOWN" in result


def test_get_host_status_not_found(mock_client_cls):
    from server import checkmk_get_host_status
    mock_client_cls.get.return_value = {"value": []}
    result = checkmk_get_host_status("ghost")
    assert "not found" in result.lower()


def test_get_host_status_error(mock_client_cls):
    from server import checkmk_get_host_status
    mock_client_cls.get.return_value = "❌ Auth failed — check CHECKMK_TOKEN"
    result = checkmk_get_host_status("us1app001")
    assert result.startswith("❌")


# ── checkmk_get_service_status ───────────────────────────────────────────────

def test_get_service_status(mock_client_cls):
    from server import checkmk_get_service_status
    mock_client_cls.get.return_value = {
        "value": [{"extensions": {"state": 2, "plugin_output": "CRIT - load 95%", "last_check": "2026-06-19 10:00"}}]
    }
    result = checkmk_get_service_status("us1app001", "CPU load")
    assert "CRIT" in result
    assert "us1app001" in result
    assert "CPU load" in result


def test_get_service_status_not_found(mock_client_cls):
    from server import checkmk_get_service_status
    mock_client_cls.get.return_value = {"value": []}
    result = checkmk_get_service_status("us1app001", "Nonexistent Service")
    assert "not found" in result.lower()


# ── checkmk_list_hosts ───────────────────────────────────────────────────────

def test_list_hosts(mock_client_cls):
    from server import checkmk_list_hosts
    mock_client_cls.get.return_value = {
        "value": [
            {"extensions": {"name": "us1app001", "address": "10.0.0.1", "state": 0}},
            {"extensions": {"name": "us1app002", "address": "10.0.0.2", "state": 1}},
        ]
    }
    result = checkmk_list_hosts()
    assert "2 host" in result
    assert "us1app001" in result
    assert "[DOWN]" in result


def test_list_hosts_empty(mock_client_cls):
    from server import checkmk_list_hosts
    mock_client_cls.get.return_value = {"value": []}
    result = checkmk_list_hosts()
    assert "No hosts found" in result


# ── checkmk_get_host_services ────────────────────────────────────────────────

def test_get_host_services(mock_client_cls):
    from server import checkmk_get_host_services
    mock_client_cls.get.return_value = {
        "value": [
            {"extensions": {"display_name": "CPU load", "state": 0, "plugin_output": "OK - 1.2"}},
            {"extensions": {"display_name": "Memory", "state": 1, "plugin_output": "WARN - 88%"}},
        ]
    }
    result = checkmk_get_host_services("us1app001")
    assert "us1app001" in result
    assert "2 service" in result
    assert "[WARN]" in result
    mock_client_cls.get.assert_called_once_with(
        "objects/host/us1app001/collections/services",
        params={"columns": ["display_name", "state", "plugin_output"]},
    )


def test_get_host_services_empty(mock_client_cls):
    from server import checkmk_get_host_services
    mock_client_cls.get.return_value = {"value": []}
    result = checkmk_get_host_services("emptyhost")
    assert "No services found" in result
