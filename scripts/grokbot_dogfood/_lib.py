from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_INSTALL_ROOT = Path.home() / ".local" / "share" / "grok-bot"
DEFAULT_CONFIG_ROOT = Path.home() / ".config" / "Grok Bot"
FEED_BASE = "https://api2.cursor.sh/updates/api/update"
USER_AGENT = "sand-dogfood"
TRACK = "dogfood"
CHANNEL = "sand-dogfood"


def install_root() -> Path:
    raw = os.environ.get("GROKBOT_DOGFOOD_INSTALL_ROOT", "")
    if raw:
        return Path(raw).expanduser()
    return DEFAULT_INSTALL_ROOT


def mask_id(value: str) -> str:
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}…{value[-4:]}"


def linux_arch() -> str:
    import platform

    machine = platform.machine().lower()
    if machine in ("aarch64", "arm64"):
        return "arm64"
    return "x64"


def read_installed_version(root: Path) -> str:
    installed = root / "installed.json"
    if installed.is_file():
        import json

        data = json.loads(installed.read_text(encoding="utf-8"))
        ver = data.get("version")
        if isinstance(ver, str) and ver.strip():
            return ver.strip()
    asar = root / "current" / "resources" / "app.asar"
    if not asar.is_file():
        asar = root / "current" / "squashfs-root" / "resources" / "app.asar"
    if asar.is_file():
        ver = _version_from_asar(asar)
        if ver:
            return ver
    return "0.0.0"


def _version_from_asar(asar: Path) -> str | None:
    try:
        proc = subprocess.run(
            [
                "npx",
                "--yes",
                "@electron/asar",
                "extract-file",
                str(asar),
                "package.json",
            ],
            capture_output=True,
            text=True,
            cwd=str(Path.cwd()),
            check=False,
        )
    except FileNotFoundError:
        return None
    pkg = Path("package.json")
    if not pkg.is_file():
        return None
    try:
        import json

        ver = json.loads(pkg.read_text(encoding="utf-8")).get("version")
        pkg.unlink(missing_ok=True)
        return str(ver) if ver else None
    except Exception:
        pkg.unlink(missing_ok=True)
        return None


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_download_url(url: str) -> None:
    if "/dogfood/" not in url or "/linux/" not in url:
        raise ValueError("download url failed dogfood/linux path checks")


def extract_appimage(appimage: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    if shutil.which("unsquashfs"):
        subprocess.run(
            ["unsquashfs", "-force", "-dest", str(dest), str(appimage)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return
    work = dest.parent / ".extract-work"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    tmp = work / "image.AppImage"
    shutil.copy2(appimage, tmp)
    tmp.chmod(0o755)
    subprocess.run(
        [str(tmp), "--appimage-extract"],
        cwd=str(work),
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    squash = work / "squashfs-root"
    if not squash.is_dir():
        raise RuntimeError("AppImage extraction failed")
    for item in squash.iterdir():
        target = dest / item.name
        if target.exists():
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
        shutil.move(str(item), str(target))
    shutil.rmtree(work, ignore_errors=True)


def write_version_env(
    dest: Path,
    version: str,
    sha256: str,
    download_url: str,
) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        "\n".join(
            [
                f"VERSION={version!r}",
                f"COMMIT_SHA={sha256!r}",
                f"DOWNLOAD_URL={download_url!r}",
                f"TRACK={TRACK!r}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def export_appimage_copy(src: Path, export_dir: Path) -> Path:
    export_dir.mkdir(parents=True, exist_ok=True)
    dest = export_dir / "grok-bot.AppImage"
    shutil.copy2(src, dest)
    dest.chmod(0o755)
    return dest
