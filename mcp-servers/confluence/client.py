from __future__ import annotations

import os
import requests

_BASE_URL = "https://confluence.8x8.com"
_CLIENT_ID = os.environ.get("CONFLUENCE_CLIENT_ID", "")
_CLIENT_SECRET = os.environ.get("CONFLUENCE_CLIENT_SECRET", "")
_TOKEN = os.environ.get("CONFLUENCE_TOKEN", "")
_TIMEOUT = int(os.environ.get("CONFLUENCE_TIMEOUT", "30"))


class ConfluenceClient:
    def __init__(self) -> None:
        if not _CLIENT_ID:
            raise ValueError("CONFLUENCE_CLIENT_ID env var is not set")
        if not _CLIENT_SECRET:
            raise ValueError("CONFLUENCE_CLIENT_SECRET env var is not set")
        if not _TOKEN:
            raise ValueError("CONFLUENCE_TOKEN env var is not set")
        self.base_url = _BASE_URL.rstrip("/")
        self.headers = {
            "CF-Access-Client-Id": _CLIENT_ID,
            "CF-Access-Client-Secret": _CLIENT_SECRET,
            "Authorization": f"Bearer {_TOKEN}",
            "Accept": "application/json",
        }
        self.timeout = _TIMEOUT

    def get(self, endpoint: str, params: dict | None = None) -> dict | str:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            resp = requests.get(url, headers=self.headers, params=params, timeout=self.timeout)
        except requests.exceptions.ConnectionError as e:
            return f"❌ Connection failed: {e}"
        except requests.exceptions.Timeout:
            return f"❌ Request timed out after {self.timeout}s"

        if resp.status_code == 401:
            return "❌ Auth failed — check CONFLUENCE_TOKEN"
        if resp.status_code == 403:
            return "❌ CF-Access rejected — check CONFLUENCE_CLIENT_ID/SECRET"
        if resp.status_code == 404:
            return f"❌ Page not found: {endpoint}"
        if resp.status_code >= 500:
            return f"❌ Server error {resp.status_code}: {resp.text[:200]}"

        try:
            return resp.json()
        except ValueError:
            return resp.text
