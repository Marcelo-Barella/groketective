#!/usr/bin/env python3
"""Fetch cursor.com changelog entries and filter Grok Bot–relevant posts."""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from html import unescape
from pathlib import Path

BASE = "https://cursor.com/changelog"
GROK_FILTER = re.compile(
    r"(?i)(\bgrok\b|\bgrok bot\b|grok-bot|\bsand[_-]|sand client|sand mobile)"
)


def fetch(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "groketective-automation/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        raise SystemExit(f"failed to fetch {url}: {exc}") from exc


def parse_page(html: str) -> list[dict]:
    entries: list[dict] = []
    seen: set[str] = set()
    for slug, published in re.findall(
        r'href="/changelog/([^"]+)"><time dateTime="([^"]+)"', html
    ):
        if slug in seen:
            continue
        seen.add(slug)
        title_match = re.search(
            rf'id="{re.escape(slug)}"[^>]*>([^<]+)', html
        )
        title = unescape(title_match.group(1).strip()) if title_match else slug
        body_match = re.search(
            rf'href="/changelog/{re.escape(slug)}"[\s\S]*?'
            rf'id="{re.escape(slug)}"[\s\S]*?</header>([\s\S]*?)</div></div></div></div></article>',
            html,
        )
        body_html = body_match.group(1) if body_match else ""
        body_text = unescape(re.sub(r"<[^>]+>", " ", body_html))
        body_text = re.sub(r"\s+", " ", body_text).strip()
        entries.append(
            {
                "slug": slug,
                "published_at": published,
                "title": title,
                "url": f"{BASE}/{slug}",
                "body_text": body_text[:4000],
            }
        )
    return entries


def load_previous(path: Path | None) -> set[str]:
    if path is None or not path.is_file():
        return set()
    if path.suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return {str(x) for x in payload}
        if isinstance(payload, dict) and "slugs" in payload:
            return set(payload["slugs"])
    return {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pages", type=int, default=3)
    parser.add_argument(
        "--filter",
        choices=("grokbot", "all"),
        default="grokbot",
        help="grokbot keeps posts matching Grok/sand keywords",
    )
    parser.add_argument("--previous-slugs", default="")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_entries: list[dict] = []
    seen_slugs: set[str] = set()
    for page in range(1, max(1, args.pages) + 1):
        url = BASE if page == 1 else f"{BASE}/page/{page}"
        html = fetch(url)
        for entry in parse_page(html):
            if entry["slug"] in seen_slugs:
                continue
            seen_slugs.add(entry["slug"])
            all_entries.append(entry)

    if args.filter == "grokbot":
        filtered = [
            e
            for e in all_entries
            if GROK_FILTER.search(e["title"] + " " + e["body_text"])
        ]
    else:
        filtered = all_entries

    previous = load_previous(
        Path(args.previous_slugs) if args.previous_slugs else None
    )
    current_slugs = {e["slug"] for e in filtered}
    new_slugs = sorted(current_slugs - previous)

    payload = {
        "source": BASE,
        "filter": args.filter,
        "fetched_count": len(all_entries),
        "filtered_count": len(filtered),
        "entries": filtered,
    }
    manifest = {
        "source": BASE,
        "filter": args.filter,
        "entry_count": len(filtered),
        "new_entry_count": len(new_slugs),
        "new_slugs": new_slugs,
        "entries_path": str(output_dir / "changelog-entries.json"),
        "slugs_path": str(output_dir / "changelog-slugs.txt"),
    }

    (output_dir / "changelog-entries.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "changelog-slugs.txt").write_text(
        "\n".join(sorted(current_slugs)) + "\n", encoding="utf-8"
    )
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    print(f"entry_count={len(filtered)}")
    print(f"new_entry_count={len(new_slugs)}")
    print(f"manifest={output_dir / 'manifest.json'}")


if __name__ == "__main__":
    main()
