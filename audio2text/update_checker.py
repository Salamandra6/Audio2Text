from __future__ import annotations

from dataclasses import dataclass

import requests
from packaging.version import InvalidVersion, Version

API_URL = "https://api.github.com/repos/Salamandra6/Audio2Text/releases/latest"


@dataclass(slots=True)
class UpdateInfo:
    available: bool
    version: str = ""
    page_url: str = ""
    notes: str = ""


def check_for_update(current_version: str, timeout: float = 5.0) -> UpdateInfo:
    response = requests.get(
        API_URL,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "Audio2Text"},
        timeout=timeout,
    )
    if response.status_code == 404:
        return UpdateInfo(False)
    response.raise_for_status()
    payload = response.json()
    tag = str(payload.get("tag_name", "")).strip().lstrip("v")
    try:
        available = Version(tag) > Version(current_version)
    except InvalidVersion:
        available = False
    return UpdateInfo(
        available=available,
        version=tag,
        page_url=str(payload.get("html_url", "")),
        notes=str(payload.get("body", ""))[:1200],
    )
