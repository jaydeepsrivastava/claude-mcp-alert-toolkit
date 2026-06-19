from __future__ import annotations

import os
import sys
import pytest
import requests
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(autouse=True)
def set_env(monkeypatch):
    monkeypatch.setenv("CHECKMK_BASE_URL", "http://fake-checkmk/site/check_mk/api/1.0")
    monkeypatch.setenv("CHECKMK_TOKEN", "automation test-token-1234")
    monkeypatch.setenv("CHECKMK_TIMEOUT", "10")
    # Reload module so env vars are picked up fresh
    import importlib
    import client as c
    importlib.reload(c)


def test_client_sends_bearer_auth():
    import client as c
    cl = c.CheckMKClient()
    assert cl.headers["Authorization"] == "Bearer automation test-token-1234"


def test_client_get_returns_json_on_200():
    import client as c
    cl = c.CheckMKClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"versions": {"checkmk": "2.2.0p11"}}
    with patch("requests.get", return_value=mock_resp) as mock_get:
        result = cl.get("version")
    assert result == {"versions": {"checkmk": "2.2.0p11"}}
    called_url = mock_get.call_args[0][0]
    assert called_url == "http://fake-checkmk/site/check_mk/api/1.0/version"


def test_client_get_returns_error_string_on_401():
    import client as c
    cl = c.CheckMKClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    with patch("requests.get", return_value=mock_resp):
        result = cl.get("version")
    assert result == "❌ Auth failed — check CHECKMK_TOKEN"


def test_client_get_returns_error_string_on_403():
    import client as c
    cl = c.CheckMKClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    with patch("requests.get", return_value=mock_resp):
        result = cl.get("version")
    assert result == "❌ Permission denied — automation user may lack access"


def test_client_get_returns_error_string_on_404():
    import client as c
    cl = c.CheckMKClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    with patch("requests.get", return_value=mock_resp):
        result = cl.get("objects/host/nonexistent")
    assert result == "❌ Not found: objects/host/nonexistent"


def test_client_get_returns_error_on_500():
    import client as c
    cl = c.CheckMKClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = "Internal error"
    with patch("requests.get", return_value=mock_resp):
        result = cl.get("version")
    assert result.startswith("❌ Server error 500:")


def test_client_get_returns_error_string_on_connection_error():
    import client as c
    cl = c.CheckMKClient()
    with patch("requests.get", side_effect=requests.exceptions.ConnectionError("refused")):
        result = cl.get("version")
    assert result.startswith("❌ Connection failed:")


def test_client_get_returns_error_string_on_timeout():
    import client as c
    cl = c.CheckMKClient()
    with patch("requests.get", side_effect=requests.exceptions.Timeout()):
        result = cl.get("version")
    assert result == "❌ Request timed out after 10s"


def test_client_raises_on_missing_base_url(monkeypatch):
    monkeypatch.delenv("CHECKMK_BASE_URL")
    import importlib
    import client as c
    importlib.reload(c)
    with pytest.raises(ValueError, match="CHECKMK_BASE_URL"):
        c.CheckMKClient()


def test_client_raises_on_missing_token(monkeypatch):
    monkeypatch.delenv("CHECKMK_TOKEN")
    import importlib
    import client as c
    importlib.reload(c)
    with pytest.raises(ValueError, match="CHECKMK_TOKEN"):
        c.CheckMKClient()
