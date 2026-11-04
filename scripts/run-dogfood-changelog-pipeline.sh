#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

while (($#)); do
  case "$1" in
    -h|--help)
      printf 'Usage: %s\n' "$0"
      printf 'Run after install-dogfood-pair.sh (dogfood-new + dogfood-previous populated).\n'
      exit 0
      ;;
    *)
      printf 'Unknown arg: %s\n' "$1" >&2
      exit 1
      ;;
  esac
done

new_dir="$ROOT_DIR/versions/dogfood-new"
previous_dir="$ROOT_DIR/versions/dogfood-previous"
new_app="$new_dir/grok-bot.AppImage"
prev_app="$previous_dir/grok-bot.AppImage"

[[ -f "$new_app" ]] || {
  printf 'Error: run scripts/install-dogfood-pair.sh first\n' >&2
  exit 1
}

timestamp=$(date -u +%Y%m%dT%H%M%SZ)
run_dir="$ROOT_DIR/workspace/runs/$timestamp"
mkdir -p "$run_dir/extract/new" "$run_dir/extract/previous" "$run_dir/plans"

"$SCRIPT_DIR/extract-appimage.sh" --appimage "$new_app" --output-dir "$run_dir/extract/new"

if [[ -f "$prev_app" ]]; then
  "$SCRIPT_DIR/extract-appimage.sh" --appimage "$prev_app" --output-dir "$run_dir/extract/previous"
  python3 "$SCRIPT_DIR/diff-build-extracts.py" \
    --previous-dir "$run_dir/extract/previous" \
    --new-dir "$run_dir/extract/new" \
    --version-env-new "$new_dir/version.env" \
    --version-env-previous "$previous_dir/version.env" \
    --output-dir "$run_dir"
else
  printf 'Warning: no previous AppImage; skipping binary diff (first dogfood baseline)\n' >&2
  python3 -c "
import json, pathlib
out = pathlib.Path('$run_dir')
payload = {'first_baseline': True, 'build_diff_path': None}
(out / 'manifest.json').write_text(json.dumps(payload, indent=2) + '\n')
print('changed_count=0')
print('app_asar_changed=false')
print(f'manifest={out / \"manifest.json\"}')
"
fi

printf 'run_dir=%s\n' "$run_dir"
printf 'manifest=%s\n' "$run_dir/manifest.json"
