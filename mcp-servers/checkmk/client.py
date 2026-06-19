from __future__ import annotations

import os
import requests

_BASE_URL = os.environ.get("CHECKMK_BASE_URL", "")
_TOKEN = os.environ.get("CHECKMK_TOKEN", "")
_TIMEOUT = int(os.environ.get("CHECKMK_TIMEOUT", "30"))


class CheckMKClient:
    def __init__(self) -> None:
        if not _BASE_URL:
            raise ValueError("CHECKMK_BASE_URL env var is not set")
        if not _TOKEN:
            raise ValueError("CHECKMK_TOKEN env var is not set")
        self.base_url = _BASE_URL.rstrip("/")
        self.headers = {
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
            return "❌ Auth failed — check CHECKMK_TOKEN"
        if resp.status_code == 403:
            return "❌ Permission denied — automation user may lack access"
        if resp.status_code == 404:
            return f"❌ Not found: {endpoint}"
        if resp.status_code >= 500:
            return f"❌ Server error {resp.status_code}: {resp.text[:200]}"

        try:
            return resp.json()
        except ValueError:
            return resp.text
