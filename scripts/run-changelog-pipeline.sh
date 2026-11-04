#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

pages=3
filter="grokbot"
previous_slugs=""

while (($#)); do
  case "$1" in
    --pages)
      (($# >= 2)) || { printf 'Error: --pages requires a value\n' >&2; exit 1; }
      pages="$2"
      shift 2
      ;;
    --filter)
      (($# >= 2)) || { printf 'Error: --filter requires a value\n' >&2; exit 1; }
      filter="$2"
      shift 2
      ;;
    --previous-slugs)
      (($# >= 2)) || { printf 'Error: --previous-slugs requires a value\n' >&2; exit 1; }
      previous_slugs="$2"
      shift 2
      ;;
    -h|--help)
      printf 'Usage: %s [--pages N] [--filter grokbot|all] [--previous-slugs PATH]\n' "$0"
      exit 0
      ;;
    *)
      printf 'Unknown arg: %s\n' "$1" >&2
      exit 1
      ;;
  esac
done

timestamp=$(date -u +%Y%m%dT%H%M%SZ)
run_dir="$ROOT_DIR/workspace/runs/$timestamp"
mkdir -p "$run_dir/plans"

fetch_args=(--pages "$pages" --filter "$filter" --output-dir "$run_dir")
if [[ -n "$previous_slugs" ]]; then
  fetch_args+=(--previous-slugs "$previous_slugs")
elif [[ -f "$ROOT_DIR/workspace/last-changelog-slugs.txt" ]]; then
  fetch_args+=(--previous-slugs "$ROOT_DIR/workspace/last-changelog-slugs.txt")
fi

python3 "$SCRIPT_DIR/fetch-changelog-entries.py" "${fetch_args[@]}"

cp -f "$run_dir/changelog-slugs.txt" "$ROOT_DIR/workspace/last-changelog-slugs.txt"
cp -f "$run_dir/changelog-entries.json" "$ROOT_DIR/workspace/last-changelog-entries.json"

printf 'run_dir=%s\n' "$run_dir"
printf 'manifest=%s\n' "$run_dir/manifest.json"
