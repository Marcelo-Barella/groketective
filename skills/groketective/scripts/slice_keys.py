#!/usr/bin/env python3
"""Encode/decode sand-client-persistence blob filenames (lowercase base32, no pad)."""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
from pathlib import Path


def b32_encode(key: str) -> str:
    return base64.b32encode(key.encode("utf-8")).decode("ascii").lower().rstrip("=")


def b32_decode(name: str) -> str:
    s = name.upper()
    pad = "=" * ((8 - len(s) % 8) % 8)
    return base64.b32decode(s + pad).decode("utf-8")


def classify_key(key: str) -> str:
    if ".transcript.replicas." in key:
        return "transcript.replicas"
    if key.endswith(".roster.last-roster") or key.endswith("roster.last-roster"):
        return "roster.last-roster"
    if key.endswith(".composer-drafts"):
        return "composer-drafts"
    if key.endswith(".sidebar.last-sections"):
        return "sidebar.last-sections"
    if key.endswith(".selection.last-agent"):
        return "selection.last-agent"
    if key.endswith(".ui-agent-refs"):
        return "ui-agent-refs"
    if key.endswith(".send-journal"):
        return "send-journal"
    if key.endswith("client-meta.account-slot") or ".client-meta." in key:
        return "client-meta"
    if key.endswith("ui-layout") or key.endswith(".ui-layout"):
        return "ui-layout"
    return "other"


def account_id_from_key(key: str) -> str:
    m = re.search(r"sand\.client\.slice\.account\.([^.]+)\.", key)
    return m.group(1) if m else ""


def agent_id_from_key(key: str) -> str:
    m = re.search(r"\.transcript\.replicas\.([0-9a-f-]{36})$", key)
    return m.group(1) if m else ""


def list_blobs(root: Path) -> list[dict]:
    rows = []
    for path in sorted(root.glob("*.blob")):
        try:
            key = b32_decode(path.stem)
        except Exception as e:
            rows.append(
                {
                    "path": str(path),
                    "size": path.stat().st_size,
                    "key": "",
                    "kind": "undecodable",
                    "error": str(e),
                }
            )
            continue
        rows.append(
            {
                "path": str(path),
                "size": path.stat().st_size,
                "key": key,
                "kind": classify_key(key),
                "account": account_id_from_key(key),
                "agent_id": agent_id_from_key(key),
            }
        )
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_enc = sub.add_parser("encode", help="base32-encode a slice key")
    p_enc.add_argument("key")

    p_dec = sub.add_parser("decode", help="base32-decode a blob stem")
    p_dec.add_argument("stem")

    p_list = sub.add_parser("list", help="list persistence blobs with decoded keys")
    p_list.add_argument("--root", default=os.path.expanduser("~/.config/Grok Bot/sand-client-persistence"))
    p_list.add_argument("--kind", default="")
    p_list.add_argument("--agent-id", default="")
    p_list.add_argument("--json", action="store_true")

    p_read = sub.add_parser("read", help="read one blob by agent-id, kind, or key substring")
    p_read.add_argument("--root", default=os.path.expanduser("~/.config/Grok Bot/sand-client-persistence"))
    p_read.add_argument("--agent-id", default="")
    p_read.add_argument("--kind", default="")
    p_read.add_argument("--key-substr", default="")
    p_read.add_argument("--max-chars", type=int, default=4000)
    p_read.add_argument("--raw", action="store_true")

    args = ap.parse_args()

    if args.cmd == "encode":
        print(b32_encode(args.key))
        return 0
    if args.cmd == "decode":
        print(b32_decode(args.stem))
        return 0
    if args.cmd == "list":
        root = Path(args.root)
        if not root.is_dir():
            print(f"error=persistence_root_missing path={root}", file=sys.stderr)
            return 1
        rows = list_blobs(root)
        if args.kind:
            rows = [r for r in rows if r.get("kind") == args.kind]
        if args.agent_id:
            rows = [r for r in rows if r.get("agent_id") == args.agent_id]
        if args.json:
            print(json.dumps(rows, indent=2))
            return 0
        print(f"blob_count={len(rows)}")
        for r in rows:
            print(
                f"kind={r.get('kind')} size={r.get('size')} agent_id={r.get('agent_id','')} key={r.get('key')}"
            )
        return 0
    if args.cmd == "read":
        root = Path(args.root)
        rows = list_blobs(root)
        matched = rows
        if args.agent_id:
            matched = [r for r in matched if r.get("agent_id") == args.agent_id]
        if args.kind:
            matched = [r for r in matched if r.get("kind") == args.kind]
        if args.key_substr:
            matched = [r for r in matched if args.key_substr in r.get("key", "")]
        if not matched:
            print("error=no_match")
            return 1
        if len(matched) > 1 and not args.agent_id and not args.key_substr:
            print(f"error=ambiguous matches={len(matched)}")
            for r in matched[:20]:
                print(f"candidate kind={r['kind']} key={r['key']}")
            return 1
        row = matched[0]
        text = Path(row["path"]).read_text(encoding="utf-8", errors="replace")
        print(f"key={row['key']}")
        print(f"kind={row['kind']}")
        print(f"path={row['path']}")
        print(f"size={row['size']}")
        if args.raw:
            print(text)
            return 0
        try:
            data = json.loads(text)
            pretty = json.dumps(data, indent=2, ensure_ascii=False)
        except Exception:
            pretty = text
        if len(pretty) > args.max_chars:
            print(pretty[: args.max_chars])
            print(f"truncated=true max_chars={args.max_chars}")
        else:
            print(pretty)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
