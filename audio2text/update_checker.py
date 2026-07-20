from __future__ import annotations

from dataclasses import dataclass

import requests
from packaging.version import InvalidVersion, Version

API_URL = "https://api.github.com/repos/Salamandra6/Audio2Text/releases/latest"


@dataclass(slots=True)
class ReleaseAsset:
    name: str
    url: str
    size: int = 0


@dataclass(slots=True)
class UpdateInfo:
    available: bool
    version: str = ""
    page_url: str = ""
    notes: str = ""
    assets: tuple[ReleaseAsset, ...] = ()

    def preferred_asset(self) -> ReleaseAsset | None:
        if not self.assets:
            return None
        ordered = sorted(
            self.assets,
            key=lambda asset: (
                0 if asset.name.lower().endswith(".exe") else 1,
                0 if "setup" in asset.name.lower() else 1,
                0 if "windows" in asset.name.lower() else 1,
                asset.name.lower(),
            ),
        )
        for asset in ordered:
            if asset.name.lower().endswith((".exe", ".msi", ".zip")):
                return asset
        return None


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

    assets = tuple(
        ReleaseAsset(
            name=str(item.get("name", "")),
            url=str(item.get("browser_download_url", "")),
            size=int(item.get("size", 0) or 0),
        )
        for item in payload.get("assets", [])
        if item.get("name") and item.get("browser_download_url")
    )
    return UpdateInfo(
        available=available,
        version=tag,
        page_url=str(payload.get("html_url", "")),
        notes=str(payload.get("body", ""))[:1200],
        assets=assets,
    )
