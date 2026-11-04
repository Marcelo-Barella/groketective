from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path

from grokbot_dogfood._lib import DEFAULT_CONFIG_ROOT, mask_id
from grokbot_dogfood.feed import OFFICIAL_BOT_PAGE, OFFICIAL_DOWNLOAD_API
from grokbot_dogfood.machine_id import MachineIdError, _decrypt_v11, _read_secrets_raw

SECRETS_KEY = "cursor-machine-id"
V11_PREFIX = b"v11"
BOOTSTRAP_WAIT_SEC = int(os.environ.get("GROKBOT_BOOTSTRAP_WAIT_SEC", "180"))


def _config_root() -> Path:
    return Path(os.environ.get("GROKBOT_CONFIG_ROOT", str(DEFAULT_CONFIG_ROOT))).expanduser()


def _secrets_path() -> Path:
    return _config_root() / "sand-secrets.json"


def fetch_official_linux_appimage(dest: Path) -> Path:
    override = os.environ.get("GROKBOT_OFFICIAL_DOWNLOAD_URL", "").strip()
    if override:
        url = override
        version = os.environ.get("GROKBOT_OFFICIAL_VERSION", "bootstrap")
        commit = os.environ.get("GROKBOT_OFFICIAL_COMMIT_SHA", "")
    else:
        api = os.environ.get("GROKBOT_OFFICIAL_DOWNLOAD_API", OFFICIAL_DOWNLOAD_API)
        req = urllib.request.Request(
            api,
            headers={
                "User-Agent": "groketective-bootstrap/1.0",
                "Referer": OFFICIAL_BOT_PAGE,
            },
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        url = payload.get("downloadUrl")
        version = payload.get("version", "bootstrap")
        commit = payload.get("commitSha", "")
        if not isinstance(url, str) or not url:
            raise MachineIdError(
                f"Official Linux download metadata missing downloadUrl "
                f"(browser page {OFFICIAL_BOT_PAGE}; headless uses {api})"
            )
    dest.mkdir(parents=True, exist_ok=True)
    out = dest / "official-grok-bot.AppImage"
    tmp = out.with_suffix(".part")
    req = urllib.request.Request(url, headers={"User-Agent": "groketective-bootstrap/1.0"})
    with urllib.request.urlopen(req, timeout=900) as resp, tmp.open("wb") as fh:
        shutil.copyfileobj(resp, fh)
    tmp.chmod(0o755)
    tmp.rename(out)
    meta = dest / "official-download.json"
    meta.write_text(
        json.dumps(
            {
                "source_page": OFFICIAL_BOT_PAGE,
                "download_url": url,
                "version": version,
                "commit_sha": commit,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return out


def _ensure_headless_session() -> None:
    if os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
        return
    if shutil.which("dbus-launch"):
        proc = subprocess.run(
            ["dbus-launch"],
            capture_output=True,
            text=True,
            check=False,
        )
        for line in proc.stdout.splitlines():
            if line.startswith("export "):
                key, _, val = line[7:].partition("=")
                os.environ[key] = val.strip().strip('"')
    if shutil.which("gnome-keyring-daemon") and not os.environ.get(
        "GNOME_KEYRING_CONTROL"
    ):
        subprocess.run(
            ["gnome-keyring-daemon", "--start", "--components=secrets"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def _launch_appimage_once(appimage: Path) -> subprocess.Popen[bytes] | None:
    _ensure_headless_session()
    env = os.environ.copy()
    env.setdefault("ELECTRON_DISABLE_SANDBOX", "1")
    env.setdefault("GROKBOT_BOOTSTRAP", "1")
    cmd: list[str]
    if shutil.which("xvfb-run"):
        cmd = [
            "xvfb-run",
            "-a",
            str(appimage),
            "--no-sandbox",
            "--disable-gpu",
            "--disable-dev-shm-usage",
        ]
    else:
        cmd = [
            str(appimage),
            "--no-sandbox",
            "--disable-gpu",
            "--disable-dev-shm-usage",
        ]
    try:
        return subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as exc:
        raise MachineIdError(f"Failed to launch Grok Bot for bootstrap: {exc}") from exc


def _machine_id_from_secrets_file(*, allow_keyring: bool) -> str | None:
    path = _secrets_path()
    if not path.is_file():
        return None
    try:
        raw = _read_secrets_raw(path)
    except MachineIdError:
        return None
    decoded = __import__("base64").b64decode(raw, validate=False)
    if decoded.startswith(V11_PREFIX):
        if not allow_keyring:
            return None
        return _decrypt_v11(decoded[3:])
    try:
        text = decoded.decode("utf-8").strip()
    except UnicodeDecodeError:
        return None
    return text or None


def bootstrap_machine_id(*, allow_keyring: bool = True) -> str:
    if os.environ.get("GROKBOT_DISABLE_BOOTSTRAP", "").lower() in ("1", "true", "yes"):
        raise MachineIdError(
            "Bootstrap disabled (GROKBOT_DISABLE_BOOTSTRAP); set GROKBOT_MACHINE_ID"
        )

    existing = _machine_id_from_secrets_file(allow_keyring=allow_keyring)
    if existing:
        return existing

    work = Path(
        os.environ.get(
            "GROKBOT_BOOTSTRAP_DIR",
            str(Path.home() / ".cache" / "groketective-bootstrap"),
        )
    ).expanduser()
    appimage = fetch_official_linux_appimage(work / "download")
    proc = _launch_appimage_once(appimage)
    deadline = time.time() + BOOTSTRAP_WAIT_SEC
    last_err: str | None = None
    while time.time() < deadline:
        try:
            mid = _machine_id_from_secrets_file(allow_keyring=allow_keyring)
            if mid:
                if proc and proc.poll() is None:
                    proc.terminate()
                return mid
        except MachineIdError as exc:
            last_err = str(exc)
        time.sleep(2)

    if proc and proc.poll() is None:
        proc.terminate()
    raise MachineIdError(
        "Timed out waiting for sand-secrets.json cursor-machine-id after official "
        f"install from {OFFICIAL_BOT_PAGE}. "
        "Headless bootstrap needs xvfb-run, a D-Bus session, and an unlocked "
        "GNOME keyring (or set GROKBOT_MACHINE_ID). "
        + (f"Last error: {last_err}" if last_err else "")
    )
