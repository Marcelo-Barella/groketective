from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path

from grokbot_dogfood._lib import (
    CHANNEL,
    TRACK,
    USER_AGENT,
    build_feed_url,
    export_appimage_copy,
    extract_appimage,
    install_root,
    mask_id,
    read_installed_version,
    sha256_file,
    validate_download_url,
    write_version_env,
)
from grokbot_dogfood.machine_id import MachineIdError, resolve_machine_id


class SyncError(RuntimeError):
    pass


def _read_installed_meta(root: Path) -> dict:
    path = root / "installed.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _resolve_cached_appimage(root: Path) -> Path | None:
    meta = _read_installed_meta(root)
    rel = meta.get("appimage")
    if isinstance(rel, str):
        candidate = root / rel
        if candidate.is_file():
            return candidate
    sha = meta.get("sha256")
    if isinstance(sha, str) and len(sha) >= 12:
        candidate = root / "cache" / f"dogfood-{sha[:12]}-0.AppImage"
        if candidate.is_file():
            return candidate
    return None


def fetch_update(installed_version: str, machine_id: str) -> tuple[str, dict] | None:
    url = build_feed_url(installed_version, machine_id)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            code = resp.getcode()
            body = resp.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 204:
            return None
        if exc.code in (401, 403):
            raise SyncError(
                "update feed rejected the request (check GROKBOT_MACHINE_ID)"
            ) from exc
        raise SyncError(f"update feed HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise SyncError(f"update feed failed: {exc}") from exc

    if code == 204 or not body.strip():
        return None
    try:
        payload = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise SyncError("update feed returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise SyncError("update feed JSON must be an object")
    return url, payload


def download_update(url: str, expected_sha256: str, cache_dir: Path) -> Path:
    validate_download_url(url)
    sha12 = expected_sha256[:12]
    dest = cache_dir / f"dogfood-{sha12}-0.AppImage"
    if dest.is_file() and sha256_file(dest) == expected_sha256:
        return dest
    tmp = dest.with_suffix(".part")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=900) as resp, tmp.open("wb") as out:
        shutil.copyfileobj(resp, out)
    digest = sha256_file(tmp)
    if digest != expected_sha256:
        tmp.unlink(missing_ok=True)
        raise SyncError("downloaded AppImage sha256 mismatch")
    tmp.rename(dest)
    dest.chmod(0o755)
    return dest


def rotate_install(root: Path, appimage: Path, version: str, sha256: str, download_url: str) -> None:
    cache_dir = root / "cache"
    staging = root / "staging" / "squashfs-root"
    current = root / "current"
    previous = root / "current.prev"
    shutil.rmtree(staging, ignore_errors=True)
    extract_appimage(appimage, staging)
    if current.exists():
        shutil.rmtree(previous, ignore_errors=True)
        current.rename(previous)
    staging.rename(current)
    installed = {
        "version": version,
        "sha256": sha256,
        "track": TRACK,
        "channel": CHANNEL,
        "url": download_url,
        "appimage": str(
            appimage.relative_to(root) if root in appimage.parents else appimage
        ),
    }
    (root / "installed.json").write_text(
        json.dumps(installed, indent=2) + "\n", encoding="utf-8"
    )


def sync_once(
    root: Path,
    *,
    export_dir: Path | None = None,
    export_previous_dir: Path | None = None,
    force_baseline_version: str | None = None,
) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    (root / "cache").mkdir(parents=True, exist_ok=True)

    try:
        machine_id = resolve_machine_id()
    except MachineIdError as exc:
        raise SyncError(str(exc)) from exc

    installed_version = force_baseline_version or read_installed_version(root)
    print(f"feed_installed_version={installed_version}")
    print(f"machine_id={mask_id(machine_id)}")

    previous_appimage: Path | None = None
    prev_meta = root / "installed.json"
    if prev_meta.is_file():
        try:
            meta = json.loads(prev_meta.read_text(encoding="utf-8"))
            rel = meta.get("appimage")
            sha = meta.get("sha256")
            if isinstance(rel, str):
                candidate = root / rel
                if candidate.is_file():
                    previous_appimage = candidate
            if previous_appimage is None and isinstance(sha, str) and len(sha) >= 12:
                candidate = root / "cache" / f"dogfood-{sha[:12]}-0.AppImage"
                if candidate.is_file():
                    previous_appimage = candidate
        except json.JSONDecodeError:
            pass
    prev_dir = root / "current.prev"
    if previous_appimage is None and prev_dir.is_dir():
        for name in ("grok-bot.AppImage", "AppRun"):
            p = prev_dir / name
            if p.is_file() and os.access(p, os.X_OK):
                previous_appimage = p
                break

    result = fetch_update(installed_version, machine_id)
    if result is None:
        current_app = _resolve_cached_appimage(root)
        if export_dir is not None and current_app is not None:
            export_appimage_copy(current_app, export_dir)
            meta = _read_installed_meta(root)
            write_version_env(
                export_dir / "version.env",
                str(meta.get("version", installed_version)),
                str(meta.get("sha256", sha256_file(current_app))),
                str(meta.get("url", "")),
            )
        if export_previous_dir is not None and previous_appimage and previous_appimage.is_file():
            export_appimage_copy(previous_appimage, export_previous_dir)
            write_version_env(
                export_previous_dir / "version.env",
                installed_version,
                sha256_file(previous_appimage),
                "",
            )
        return {
            "updated": False,
            "installed_version": installed_version,
            "machine_id_masked": mask_id(machine_id),
            "previous_appimage": str(previous_appimage) if previous_appimage else "",
            "current_appimage": str(current_app) if current_app else "",
        }

    _feed_url, payload = result
    version = payload.get("version")
    url = payload.get("url")
    sha = payload.get("sha256hash") or payload.get("sha256")
    if not all(isinstance(x, str) and x for x in (version, url, sha)):
        raise SyncError("update JSON missing version, url, or sha256hash")

    appimage = download_update(url, sha, root / "cache")
    old_meta = _read_installed_meta(root)
    if export_previous_dir is not None and previous_appimage and previous_appimage.is_file():
        export_appimage_copy(previous_appimage, export_previous_dir)
        write_version_env(
            export_previous_dir / "version.env",
            str(old_meta.get("version", installed_version)),
            str(old_meta.get("sha256", sha256_file(previous_appimage))),
            str(old_meta.get("url", "")),
        )
    rotate_install(root, appimage, version, sha, url)

    if export_dir is not None:
        export_appimage_copy(appimage, export_dir)
        write_version_env(export_dir / "version.env", version, sha, url)

    return {
        "updated": True,
        "version": version,
        "sha256": sha,
        "download_url": url,
        "machine_id_masked": mask_id(machine_id),
        "appimage": str(appimage),
        "previous_appimage": str(previous_appimage) if previous_appimage else "",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Grok Bot dogfood sync (sync.py equivalent)")
    parser.add_argument(
        "--install-root",
        default="",
        help="default: GROKBOT_DOGFOOD_INSTALL_ROOT or ~/.local/share/grok-bot",
    )
    parser.add_argument(
        "--export-dir",
        default="",
        help="copy new AppImage + version.env here (automation)",
    )
    parser.add_argument(
        "--export-previous-dir",
        default="",
        help="copy pre-update AppImage + version.env here",
    )
    parser.add_argument(
        "--baseline-version",
        default="",
        help="override installed version for feed check (first install)",
    )
    args = parser.parse_args(argv)

    root = Path(args.install_root).expanduser() if args.install_root else install_root()
    export_dir = Path(args.export_dir).expanduser() if args.export_dir else None
    export_previous_dir = (
        Path(args.export_previous_dir).expanduser() if args.export_previous_dir else None
    )

    try:
        outcome = sync_once(
            root,
            export_dir=export_dir,
            export_previous_dir=export_previous_dir,
            force_baseline_version=args.baseline_version or None,
        )
    except SyncError as exc:
        print(f"error={exc}", file=sys.stderr)
        return 2

    if not outcome.get("updated"):
        print("updated=false")
        print(f"installed_version={outcome.get('installed_version')}")
        return 0

    print("updated=true")
    print(f"version={outcome.get('version')}")
    print(f"sha256={outcome.get('sha256')}")
    print(f"download_url={outcome.get('download_url')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
