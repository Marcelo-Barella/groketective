#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

usage() {
  printf 'Usage: %s [--first-run] [--previous-url URL --previous-version VER --previous-commit SHA]\n' "$0"
}

die() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

first_run=false
previous_url=""
previous_version=""
previous_commit=""
new_dir="$ROOT_DIR/versions/new"
previous_dir="$ROOT_DIR/versions/previous"

while (($#)); do
  case "$1" in
    --first-run)
      first_run=true
      shift
      ;;
    --previous-url)
      (($# >= 2)) || die "--previous-url requires a value"
      previous_url="$2"
      shift 2
      ;;
    --previous-version)
      (($# >= 2)) || die "--previous-version requires a value"
      previous_version="$2"
      shift 2
      ;;
    --previous-commit)
      (($# >= 2)) || die "--previous-commit requires a value"
      previous_commit="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "Unknown argument: $1"
      ;;
  esac
done

mkdir -p "$new_dir" "$previous_dir"

printf 'Installing new Grok Bot stable build...\n'
"$SCRIPT_DIR/update-grokbot.sh" \
  --track stable \
  --install-dir "$new_dir" \
  --appimage-only

if [[ "$first_run" == true ]]; then
  printf 'First run: recording baseline (same stable channel; skip uses commit diff on later runs)...\n'
  cp -a "$new_dir/." "$previous_dir/"
else
  [[ -n "$previous_url" && -n "$previous_version" ]] || die "previous build metadata required after first run"
  printf 'Installing previous Grok Bot build from memory...\n'
  "$SCRIPT_DIR/update-grokbot.sh" \
    --url "$previous_url" \
    --version "$previous_version" \
    --commit "${previous_commit:-}" \
    --install-dir "$previous_dir" \
    --appimage-only
fi

new_env="$new_dir/version.env"
previous_env="$previous_dir/version.env"
[[ -f "$new_env" && -f "$previous_env" ]] || die "version.env missing after install"

# shellcheck disable=SC1090
source "$new_env"
new_version="$VERSION"
new_commit="$COMMIT_SHA"
new_download_url="$DOWNLOAD_URL"

if [[ "$first_run" != true && -n "$previous_commit" && "$new_commit" == "$previous_commit" ]]; then
  printf 'skip=true\n'
  printf 'reason=same_commit\n'
  printf 'commit_sha=%s\n' "$new_commit"
  exit 0
fi

printf 'skip=false\n'
printf 'is_first_run=%s\n' "$first_run"
printf 'new_version=%s\n' "$new_version"
printf 'new_commit=%s\n' "$new_commit"
printf 'new_download_url=%s\n' "$new_download_url"
printf 'new_dir=%s\n' "$new_dir"
printf 'previous_dir=%s\n' "$previous_dir"
