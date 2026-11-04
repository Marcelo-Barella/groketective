#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
export PYTHONPATH="${SCRIPT_DIR}${PYTHONPATH:+:${PYTHONPATH}}"

usage() {
  printf 'Usage: %s [--first-run] [--previous-commit SHA]\n' "$0"
  printf '\nUses api2.cursor.sh sand-dogfood feed (see .cursor/skills/install-grokbot-dogfood/SKILL.md).\n'
  printf 'Machine id: GROKBOT_MACHINE_ID env, else decrypt sand-secrets + keyring.\n'
}

die() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

first_run=false
memory_previous_commit=""

while (($#)); do
  case "$1" in
    --first-run) first_run=true; shift ;;
    --previous-commit)
      (($# >= 2)) || die "--previous-commit requires a value"
      memory_previous_commit="$2"
      shift 2
      ;;
    -h|--help) usage; exit 0 ;;
    *) die "Unknown argument: $1" ;;
  esac
done

sync_root="${GROKBOT_DOGFOOD_SYNC_ROOT:-$ROOT_DIR/versions/grok-bot-dogfood}"
new_dir="$ROOT_DIR/versions/dogfood-new"
previous_dir="$ROOT_DIR/versions/dogfood-previous"
mkdir -p "$sync_root" "$new_dir" "$previous_dir"

sync_args=(
  --install-root "$sync_root"
  --export-dir "$new_dir"
  --export-previous-dir "$previous_dir"
)
if [[ "$first_run" == true ]]; then
  sync_args+=(--baseline-version "0.0.0")
fi

set +e
sync_out="$(python3 "$SCRIPT_DIR/grokbot_dogfood/sync.py" "${sync_args[@]}" 2>&1)"
sync_rc=$?
set -e
printf '%s\n' "$sync_out"
if (( sync_rc == 2 )); then
  exit 2
fi
if (( sync_rc != 0 )); then
  die "dogfood sync failed (exit $sync_rc)"
fi

new_env="$new_dir/version.env"
[[ -f "$new_env" ]] || die "version.env missing after sync (export failed or no install)"

# shellcheck disable=SC1090
source "$new_env"
new_version="$VERSION"
new_commit="$COMMIT_SHA"
new_download_url="$DOWNLOAD_URL"

if [[ "$first_run" == true ]]; then
  if [[ ! -f "$previous_dir/grok-bot.AppImage" ]]; then
    cp -a "$new_dir/." "$previous_dir/"
  fi
fi

if [[ ! -f "$previous_dir/grok-bot.AppImage" ]]; then
  printf 'Warning: previous export missing; diff may be empty until second dogfood bump\n' >&2
fi

if [[ "$first_run" != true && -n "$memory_previous_commit" && "$new_commit" == "$memory_previous_commit" ]]; then
  if grep -q '^updated=false' <<<"$sync_out"; then
    printf 'skip=true\n'
    printf 'reason=same_commit_no_feed_update\n'
    printf 'commit_sha=%s\n' "$new_commit"
    exit 0
  fi
fi

if grep -q '^updated=false' <<<"$sync_out"; then
  printf 'skip=true\n'
  printf 'reason=no_feed_update\n'
  printf 'commit_sha=%s\n' "$new_commit"
  exit 0
fi

printf 'skip=false\n'
printf 'is_first_run=%s\n' "$first_run"
printf 'dogfood_version=%s\n' "$new_version"
printf 'dogfood_commit=%s\n' "$new_commit"
printf 'dogfood_download_url=%s\n' "$new_download_url"
printf 'sync_root=%s\n' "$sync_root"
printf 'new_dir=%s\n' "$new_dir"
printf 'previous_dir=%s\n' "$previous_dir"
