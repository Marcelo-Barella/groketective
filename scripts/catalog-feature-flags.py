#!/usr/bin/env python3
"""Extract Grok Bot client feature gates from resources/app.asar (strings scan)."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_PATTERN = re.compile(
    r"([a-zA-Z0-9_]+):\{client:(!0|!1),default:(!0|!1)\}"
)
FALLBACK_PATTERN = re.compile(
    r"([a-zA-Z0-9_]+):\{client:(!0|!1),fallbackValues:\{"
)
ENABLED_FALLBACK = re.compile(
    r"([a-zA-Z0-9_]+):\{client:(!0|!1),fallbackValues:\{enabled:(!0|!1)"
)


def find_app_asar(extract_dir: Path) -> Path:
    direct = extract_dir / "resources" / "app.asar"
    if direct.is_file():
        return direct
    matches = list(extract_dir.rglob("app.asar"))
    matches = [p for p in matches if "app.asar.unpacked" not in str(p)]
    if not matches:
        raise SystemExit(f"app.asar not found under {extract_dir}")
    matches.sort(key=lambda p: len(str(p)))
    return matches[0]


def read_asar_strings(asar: Path) -> str:
    try:
        proc = subprocess.run(
            ["strings", str(asar)],
            capture_output=True,
            text=True,
            errors="replace",
            check=True,
        )
    except FileNotFoundError as exc:
        raise SystemExit("strings(1) is required to scan app.asar") from exc
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"strings failed on {asar}: {exc}") from exc
    return proc.stdout


def category_for(name: str) -> str:
    prefix = name.split("_", 1)[0]
    mapping = {
        "grok": "grok",
        "sand": "sand",
        "glass": "glass",
        "cloud": "cloud",
        "agent": "agent",
        "composer": "composer",
        "mcp": "mcp",
        "automations": "automations",
        "browser": "browser",
        "mobile": "mobile",
        "messaging": "messaging",
        "show": "ui",
        "customize": "ui",
    }
    return mapping.get(prefix, "other")


def load_names(path: Path | None) -> set[str]:
    if path is None or not path.is_file():
        return set()
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        payload = json.loads(text)
        if isinstance(payload, dict) and "flags" in payload:
            return {f["name"] for f in payload["flags"]}
        if isinstance(payload, list):
            return {str(x) for x in payload}
        raise SystemExit(f"unsupported previous catalog JSON shape: {path}")
    return {line.strip() for line in text.splitlines() if line.strip()}


def parse_flags(data: str) -> list[dict]:
    by_name: dict[str, dict] = {}

    for name, client, default in DEFAULT_PATTERN.findall(data):
        by_name[name] = {
            "name": name,
            "client": client == "!0",
            "default": default == "!0",
            "shape": "default",
        }

    for name, client, enabled in ENABLED_FALLBACK.findall(data):
        entry = by_name.get(name)
        if entry is None:
            by_name[name] = {
                "name": name,
                "client": client == "!0",
                "default": enabled == "!0",
                "shape": "fallbackValues",
            }
        elif entry.get("shape") != "default":
            entry["default"] = enabled == "!0"
            entry["shape"] = "fallbackValues"

    for name, client in FALLBACK_PATTERN.findall(data):
        if name in by_name:
            continue
        by_name[name] = {
            "name": name,
            "client": client == "!0",
            "default": None,
            "shape": "fallbackValues",
        }

    flags = sorted(by_name.values(), key=lambda f: f["name"])
    if not flags:
        raise SystemExit("no client feature gate entries matched in app.asar")
    return flags


def load_version_env(env_path: Path) -> tuple[str, str, str]:
    version = ""
    commit_sha = ""
    download_url = ""
    if not env_path.is_file():
        return version, commit_sha, download_url
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("VERSION="):
            version = line.split("=", 1)[1].strip().strip("'\"")
        elif line.startswith("COMMIT_SHA="):
            commit_sha = line.split("=", 1)[1].strip().strip("'\"")
        elif line.startswith("DOWNLOAD_URL="):
            download_url = line.split("=", 1)[1].strip().strip("'\"")
    return version, commit_sha, download_url


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--extract-dir", required=True)
    parser.add_argument("--version-env", required=True)
    parser.add_argument("--previous-names", default="")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    extract_dir = Path(args.extract_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    version, commit_sha, download_url = load_version_env(Path(args.version_env))
    asar = find_app_asar(extract_dir)
    data = read_asar_strings(asar)
    flags = parse_flags(data)
    names = [f["name"] for f in flags]
    previous = load_names(Path(args.previous_names) if args.previous_names else None)
    current = set(names)
    new_flags = sorted(current - previous)
    removed_flags = sorted(previous - current)

    inventory = {
        "source": "client gates in resources/app.asar (strings scan)",
        "product": "Grok Bot (sand)",
        "version": version,
        "commit_sha": commit_sha,
        "download_url": download_url,
        "app_asar": str(asar),
        "count": len(flags),
        "flags": flags,
    }
    manifest = {
        "product": "Grok Bot (sand)",
        "version": version,
        "commit_sha": commit_sha,
        "download_url": download_url,
        "app_asar": str(asar),
        "flag_count": len(flags),
        "new_flags_count": len(new_flags),
        "removed_flags_count": len(removed_flags),
        "new_flags": [
            {
                "name": name,
                "client": next(f["client"] for f in flags if f["name"] == name),
                "default": next(f["default"] for f in flags if f["name"] == name),
                "category": category_for(name),
            }
            for name in new_flags
        ],
        "removed_flags": removed_flags,
        "inventory_path": str(output_dir / "feature-flags-inventory.json"),
        "names_path": str(output_dir / "feature-flags-names.txt"),
    }

    (output_dir / "feature-flags-inventory.json").write_text(
        json.dumps(inventory, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "feature-flags-names.txt").write_text(
        "\n".join(names) + "\n", encoding="utf-8"
    )
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    print(f"app_asar={asar}")
    print(f"flag_count={len(flags)}")
    print(f"new_flags_count={len(new_flags)}")
    print(f"removed_flags_count={len(removed_flags)}")
    print(f"manifest={output_dir / 'manifest.json'}")


if __name__ == "__main__":
    main()
