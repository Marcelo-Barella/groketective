#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

usage() {
  printf 'Usage: %s [--first-run] [--previous-url URL --previous-version VER --previous-commit SHA]\n' "$0"
  printf '\nDogfood download (when public API fails):\n'
  printf '  Set Automation Memory or env: GROKBOT_DOGFOOD_DOWNLOAD_URL, GROKBOT_DOGFOOD_VERSION,\n'
  printf '  optional GROKBOT_DOGFOOD_COMMIT_SHA for the latest build.\n'
}

die() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

first_run=false
previous_url=""
previous_version=""
previous_commit=""
new_dir="$ROOT_DIR/versions/dogfood-new"
previous_dir="$ROOT_DIR/versions/dogfood-previous"

while (($#)); do
  case "$1" in
    --first-run) first_run=true; shift ;;
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
    -h|--help) usage; exit 0 ;;
    *) die "Unknown argument: $1" ;;
  esac
done

mkdir -p "$new_dir" "$previous_dir"

install_latest_dogfood() {
  local target_dir="$1"
  if [[ -n "${GROKBOT_DOGFOOD_DOWNLOAD_URL:-}" && -n "${GROKBOT_DOGFOOD_VERSION:-}" ]]; then
    "$SCRIPT_DIR/update-grokbot.sh" \
      --url "$GROKBOT_DOGFOOD_DOWNLOAD_URL" \
      --version "$GROKBOT_DOGFOOD_VERSION" \
      --commit "${GROKBOT_DOGFOOD_COMMIT_SHA:-}" \
      --install-dir "$target_dir" \
      --appimage-only
    return 0
  fi
  if "$SCRIPT_DIR/update-grokbot.sh" \
    --track dogfood \
    --install-dir "$target_dir" \
    --appimage-only 2>/dev/null; then
    return 0
  fi
  cat >&2 <<'EOF'
Error: Grok Bot dogfood build is not available from the public download API
(releaseTrack=dogfood returns HTTP 500 for appName=sand).

Stub — configure one of:
  • Automation Memory: dogfood_download_url, dogfood_version, dogfood_commit_sha
  • Environment: GROKBOT_DOGFOOD_DOWNLOAD_URL, GROKBOT_DOGFOOD_VERSION, GROKBOT_DOGFOOD_COMMIT_SHA

Obtain the dogfood AppImage/deb from your internal dogfood channel (same source Marcelo
uses for the Cursor Changelogs automation on Cursor dev builds).
EOF
  exit 2
}

printf 'Installing latest Grok Bot dogfood build...\n'
install_latest_dogfood "$new_dir"

if [[ "$first_run" == true ]]; then
  printf 'First run: copying dogfood baseline into previous/\n'
  cp -a "$new_dir/." "$previous_dir/"
else
  [[ -n "$previous_url" && -n "$previous_version" ]] || die "previous dogfood metadata required after first run"
  printf 'Installing previous dogfood build from memory...\n'
  "$SCRIPT_DIR/update-grokbot.sh" \
    --url "$previous_url" \
    --version "$previous_version" \
    --commit "${previous_commit:-}" \
    --install-dir "$previous_dir" \
    --appimage-only
fi

new_env="$new_dir/version.env"
[[ -f "$new_env" ]] || die "version.env missing after dogfood install"
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
printf 'dogfood_version=%s\n' "$new_version"
printf 'dogfood_commit=%s\n' "$new_commit"
printf 'dogfood_download_url=%s\n' "$new_download_url"
printf 'new_dir=%s\n' "$new_dir"
printf 'previous_dir=%s\n' "$previous_dir"
