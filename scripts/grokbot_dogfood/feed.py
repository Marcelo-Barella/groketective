from __future__ import annotations

OFFICIAL_BOT_PAGE = "https://x.ai/bot"
OFFICIAL_DOWNLOAD_API = (
    "https://cursor.com/api/download?platform=linux-x64&releaseTrack=stable&appName=sand"
)

FEED_BASE = "https://api2.cursor.sh/updates/api/update"
CHANNEL = "sand-dogfood"


def linux_arch() -> str:
    import platform

    machine = platform.machine().lower()
    if machine in ("aarch64", "arm64"):
        return "arm64"
    return "x64"


def prerelease_tag(version: str) -> str:
    if "-" not in version:
        return "stable"
    tag = version.split("-", 1)[1].split(".", 1)[0]
    return tag or "stable"


def needs_track_changed(installed_version: str) -> bool:
    return prerelease_tag(installed_version) != "dogfood"


def build_feed_url(installed_version: str, machine_id: str) -> str:
    arch = linux_arch()
    url = (
        f"{FEED_BASE}/linux-{arch}/{CHANNEL}/"
        f"{installed_version}/{machine_id}/stable"
    )
    if needs_track_changed(installed_version):
        url += "?trackChanged=1"
    return url
