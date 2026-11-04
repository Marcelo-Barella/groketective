#!/usr/bin/env python3
"""Diff two Grok Bot AppImage extract trees; rank important path changes."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

PRIORITY_PREFIXES = (
    "resources/app.asar",
    "resources/app.asar.unpacked/dist/electron-main/",
    "resources/app.asar.unpacked/dist/local-exec-daemon/",
    "resources/app.asar.unpacked/dist/host/",
    "resources/app.asar.unpacked/dist/electron-preload/",
    "usr/share/",
    "sand",
    "grok-bot",
)

ASAR_INNER_PRIORITY = (
    "package.json",
    "dist/electron-main/main.cjs",
    "dist/local-exec-daemon/main.cjs",
    "dist/host/host-main.cjs",
    "dist/renderer/assets/",
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def collect_files(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not root.is_dir():
        return out
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        out[rel] = sha256_file(path)
    return out


def importance(rel: str) -> int:
    score = 0
    for i, prefix in enumerate(PRIORITY_PREFIXES):
        if rel.startswith(prefix) or prefix in rel:
            score = max(score, 100 - i * 5)
    if rel.endswith(".AppImage") or rel.endswith("app.asar"):
        score = max(score, 100)
    return score


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--previous-dir", required=True)
    parser.add_argument("--new-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--version-env-new", default="")
    parser.add_argument("--version-env-previous", default="")
    args = parser.parse_args()

    previous_dir = Path(args.previous_dir)
    new_dir = Path(args.new_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    prev_files = collect_files(previous_dir)
    new_files = collect_files(new_dir)
    prev_set = set(prev_files)
    new_set = set(new_files)

    added = sorted(new_set - prev_set)
    removed = sorted(prev_set - new_set)
    changed = sorted(
        rel for rel in prev_set & new_set if prev_files[rel] != new_files[rel]
    )

    def enrich(rels: list[str], change_type: str) -> list[dict]:
        rows = []
        for rel in rels:
            rows.append(
                {
                    "path": rel,
                    "change": change_type,
                    "importance": importance(rel),
                    "previous_sha256": prev_files.get(rel),
                    "new_sha256": new_files.get(rel),
                }
            )
        rows.sort(key=lambda r: (-r["importance"], r["path"]))
        return rows

    changes = (
        enrich(changed, "modified")
        + enrich(added, "added")
        + enrich(removed, "removed")
    )
    changes.sort(key=lambda r: (-r["importance"], r["path"]))

    asar_rel = "resources/app.asar"
    manifest = {
        "previous_dir": str(previous_dir),
        "new_dir": str(new_dir),
        "previous_file_count": len(prev_files),
        "new_file_count": len(new_files),
        "changed_count": len(changed),
        "added_count": len(added),
        "removed_count": len(removed),
        "app_asar_changed": asar_rel in changed
        or asar_rel in added
        or asar_rel in removed,
        "important_changes": changes[:200],
        "asar_inner_focus": list(ASAR_INNER_PRIORITY),
        "version_env_new": args.version_env_new,
        "version_env_previous": args.version_env_previous,
    }

    (output_dir / "build-diff.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "manifest.json").write_text(
        json.dumps(
            {
                "changed_count": manifest["changed_count"],
                "added_count": manifest["added_count"],
                "removed_count": manifest["removed_count"],
                "app_asar_changed": manifest["app_asar_changed"],
                "build_diff_path": str(output_dir / "build-diff.json"),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"changed_count={manifest['changed_count']}")
    print(f"app_asar_changed={manifest['app_asar_changed']}")
    print(f"manifest={output_dir / 'manifest.json'}")


if __name__ == "__main__":
    main()
