#!/usr/bin/env python3
"""List shared client gates that still need Grok Bot (sand) gap-fill work vs Notion Keys."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_keys(path: Path | None) -> set[str]:
    if path is None or not path.is_file():
        return set()
    return {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", required=True, help="feature-flags-inventory.json")
    parser.add_argument(
        "--notion-keys",
        default="",
        help="one Notion Key per line (Cursor Feature Flags database)",
    )
    parser.add_argument(
        "--notion-done-keys",
        default="",
        help="Keys already Done by cursor-detective (skip unless --include-done)",
    )
    parser.add_argument("--include-done", action="store_true")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    inventory = json.loads(Path(args.inventory).read_text(encoding="utf-8"))
    flags = inventory.get("flags") or []
    notion_keys = load_keys(Path(args.notion_keys) if args.notion_keys else None)
    done_keys = load_keys(Path(args.notion_done_keys) if args.notion_done_keys else None)

    missing_in_notion = []
    revisit = []
    for f in flags:
        name = f["name"]
        if name not in notion_keys:
            missing_in_notion.append(f)
        elif not args.include_done and name in done_keys:
            continue
        elif name in notion_keys and name not in done_keys:
            revisit.append(f)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "notion_database": "Cursor Feature Flags",
        "shared_registry_note": "Grok Bot app.asar and Cursor workbench kFe expose the same client gate keys",
        "catalog_count": len(flags),
        "missing_in_notion_count": len(missing_in_notion),
        "revisit_in_notion_count": len(revisit),
        "missing_in_notion": missing_in_notion,
        "revisit_in_notion": revisit,
        "gap_flags": missing_in_notion + revisit,
    }
    (output_dir / "notion-flag-gaps.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    names = [f["name"] for f in payload["gap_flags"]]
    (output_dir / "gap-flag-names.txt").write_text(
        "\n".join(names) + ("\n" if names else ""), encoding="utf-8"
    )
    print(f"gap_count={len(names)}")
    print(f"gaps_path={output_dir / 'notion-flag-gaps.json'}")


if __name__ == "__main__":
    main()
