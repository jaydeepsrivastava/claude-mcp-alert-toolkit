from __future__ import annotations

import os
import sys
import pytest
import requests
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(autouse=True)
def set_env(monkeypatch):
    monkeypatch.setenv("CONFLUENCE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("CONFLUENCE_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("CONFLUENCE_TOKEN", "test-bearer-token")
    import importlib
    import client as c
    importlib.reload(c)


def test_client_sends_cf_access_headers():
    import client as c
    cl = c.ConfluenceClient()
    assert cl.headers["CF-Access-Client-Id"] == "test-client-id"
    assert cl.headers["CF-Access-Client-Secret"] == "test-client-secret"


def test_client_sends_bearer_auth():
    import client as c
    cl = c.ConfluenceClient()
    assert cl.headers["Authorization"] == "Bearer test-bearer-token"


def test_client_get_returns_json_on_200():
    import client as c
    cl = c.ConfluenceClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"results": [], "size": 0}
    with patch("requests.get", return_value=mock_resp) as mock_get:
        result = cl.get("rest/api/space", params={"limit": 1})
    assert result == {"results": [], "size": 0}
    called_url = mock_get.call_args[0][0]
    assert called_url == "https://confluence.8x8.com/rest/api/space"


def test_client_get_returns_error_on_401():
    import client as c
    cl = c.ConfluenceClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    with patch("requests.get", return_value=mock_resp):
        result = cl.get("rest/api/space")
    assert result == "❌ Auth failed — check CONFLUENCE_TOKEN"


def test_client_get_returns_error_on_403():
    import client as c
    cl = c.ConfluenceClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    with patch("requests.get", return_value=mock_resp):
        result = cl.get("rest/api/space")
    assert result == "❌ CF-Access rejected — check CONFLUENCE_CLIENT_ID/SECRET"


def test_client_get_returns_error_on_404():
    import client as c
    cl = c.ConfluenceClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    with patch("requests.get", return_value=mock_resp):
        result = cl.get("rest/api/content/9999999")
    assert result == "❌ Page not found: rest/api/content/9999999"


def test_client_get_returns_error_on_500():
    import client as c
    cl = c.ConfluenceClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = "Internal Server Error"
    with patch("requests.get", return_value=mock_resp):
        result = cl.get("rest/api/space")
    assert result.startswith("❌ Server error 500:")


def test_client_get_returns_error_on_connection_error():
    import client as c
    cl = c.ConfluenceClient()
    with patch("requests.get", side_effect=requests.exceptions.ConnectionError("refused")):
        result = cl.get("rest/api/space")
    assert result.startswith("❌ Connection failed:")


def test_client_get_returns_error_on_timeout():
    import client as c
    cl = c.ConfluenceClient()
    with patch("requests.get", side_effect=requests.exceptions.Timeout()):
        result = cl.get("rest/api/space")
    assert result == "❌ Request timed out after 30s"


def test_client_raises_on_missing_client_id(monkeypatch):
    monkeypatch.delenv("CONFLUENCE_CLIENT_ID")
    import importlib
    import client as c
    importlib.reload(c)
    with pytest.raises(ValueError, match="CONFLUENCE_CLIENT_ID"):
        c.ConfluenceClient()


def test_client_raises_on_missing_client_secret(monkeypatch):
    monkeypatch.delenv("CONFLUENCE_CLIENT_SECRET")
    import importlib
    import client as c
    importlib.reload(c)
    with pytest.raises(ValueError, match="CONFLUENCE_CLIENT_SECRET"):
        c.ConfluenceClient()


def test_client_raises_on_missing_token(monkeypatch):
    monkeypatch.delenv("CONFLUENCE_TOKEN")
    import importlib
    import client as c
    importlib.reload(c)
    with pytest.raises(ValueError, match="CONFLUENCE_TOKEN"):
        c.ConfluenceClient()
