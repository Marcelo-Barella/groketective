#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

previous_names=""

while (($#)); do
  case "$1" in
    --previous-names)
      (($# >= 2)) || { printf 'Error: --previous-names requires a value\n' >&2; exit 1; }
      previous_names="$2"
      shift 2
      ;;
    -h|--help)
      printf 'Usage: %s [--previous-names PATH]\n' "$0"
      exit 0
      ;;
    *)
      printf 'Unknown arg: %s\n' "$1" >&2
      exit 1
      ;;
  esac
done

new_dir="$ROOT_DIR/versions/new"
new_env="$new_dir/version.env"

[[ -f "$new_dir/grok-bot.AppImage" ]] || {
  printf 'Error: run scripts/install-pair.sh first\n' >&2
  exit 1
}
[[ -f "$new_env" ]] || {
  printf 'Error: missing %s\n' "$new_env" >&2
  exit 1
}

timestamp=$(date -u +%Y%m%dT%H%M%SZ)
run_dir="$ROOT_DIR/workspace/runs/$timestamp"
mkdir -p "$run_dir/extract/new" "$run_dir/plans"

"$SCRIPT_DIR/extract-appimage.sh" \
  --appimage "$new_dir/grok-bot.AppImage" \
  --output-dir "$run_dir/extract/new"

catalog_args=(
  --extract-dir "$run_dir/extract/new"
  --version-env "$new_env"
  --output-dir "$run_dir"
)
if [[ -n "$previous_names" ]]; then
  catalog_args+=(--previous-names "$previous_names")
elif [[ -f "$ROOT_DIR/workspace/last-feature-flags-names.txt" ]]; then
  catalog_args+=(--previous-names "$ROOT_DIR/workspace/last-feature-flags-names.txt")
fi

python3 "$SCRIPT_DIR/catalog-feature-flags.py" "${catalog_args[@]}"

cp -f "$run_dir/feature-flags-names.txt" "$ROOT_DIR/workspace/last-feature-flags-names.txt"
cp -f "$run_dir/feature-flags-inventory.json" "$ROOT_DIR/workspace/last-feature-flags-inventory.json"

printf 'run_dir=%s\n' "$run_dir"
printf 'manifest=%s\n' "$run_dir/manifest.json"
printf 'app_asar=%s\n' "$(python3 -c "import json; print(json.load(open('$run_dir/manifest.json'))['app_asar'])")"
