#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

readonly DEFAULT_API_URL="https://cursor.com/api/download"
readonly DEFAULT_ICON_URL="https://cursor.com/favicon.ico"
readonly APP_DISPLAY_NAME="Grok Bot"
readonly APP_ID="grok-bot"

api_url="${GROKBOT_API_URL:-$DEFAULT_API_URL}"
platform="${GROKBOT_PLATFORM:-linux-x64}"
release_track="${GROKBOT_RELEASE_TRACK:-stable}"
app_name="${GROKBOT_APP_NAME:-sand}"
install_dir="${GROKBOT_INSTALL_DIR:-$HOME/Applications/grok-bot}"
icon_url="${GROKBOT_ICON_URL:-$DEFAULT_ICON_URL}"
xdg_data_home="${XDG_DATA_HOME:-$HOME/.local/share}"
direct_url=""
direct_version=""
direct_commit=""
appimage_only=false

appimage_path="$install_dir/grok-bot.AppImage"
icon_path="$install_dir/grok-bot.ico"
metadata_path="$install_dir/version.env"
desktop_file="$xdg_data_home/applications/$APP_ID.desktop"

tmp_appimage=""
tmp_icon=""
tmp_metadata=""
tmp_desktop=""

usage() {
  printf 'Usage: %s [--track stable|dev|latest] [--url URL] [--version VER] [--commit SHA]\n' "$0"
  printf '       [--install-dir DIR] [--appimage-only] [--app-name NAME]\n'
  printf '\nEnvironment overrides: GROKBOT_API_URL, GROKBOT_PLATFORM, GROKBOT_RELEASE_TRACK,\n'
  printf 'GROKBOT_APP_NAME, GROKBOT_INSTALL_DIR, GROKBOT_ICON_URL, XDG_DATA_HOME\n'
}

die() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

cleanup() {
  [[ -n "$tmp_appimage" && -e "$tmp_appimage" ]] && rm -f -- "$tmp_appimage"
  [[ -n "$tmp_icon" && -e "$tmp_icon" ]] && rm -f -- "$tmp_icon"
  [[ -n "$tmp_metadata" && -e "$tmp_metadata" ]] && rm -f -- "$tmp_metadata"
  [[ -n "$tmp_desktop" && -e "$tmp_desktop" ]] && rm -f -- "$tmp_desktop"
  return 0
}
trap cleanup EXIT

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

validate_token() {
  local value="$1"
  local label="$2"
  [[ "$value" =~ ^[A-Za-z0-9._-]+$ ]] || die "$label contains unsupported characters: $value"
}

validate_https_url() {
  local url="$1"
  local label="$2"
  python3 - "$url" "$label" <<'PY'
import sys
from urllib.parse import urlparse

url, label = sys.argv[1], sys.argv[2]
parsed = urlparse(url)
if parsed.scheme != "https" or not parsed.netloc:
    raise SystemExit(f"{label} must be an absolute HTTPS URL")
if any(ord(char) < 32 for char in url):
    raise SystemExit(f"{label} contains control characters")
PY
}

build_api_url() {
  python3 - "$api_url" "$platform" "$release_track" "$app_name" <<'PY'
import sys
from urllib.parse import urlencode

api_url, platform, release_track, app_name = sys.argv[1:]
query = {"platform": platform, "releaseTrack": release_track}
if app_name:
    query["appName"] = app_name
separator = "&" if "?" in api_url else "?"
print(f"{api_url}{separator}{urlencode(query)}")
PY
}

fetch_release_metadata() {
  local metadata_json="$1"
  METADATA_JSON="$metadata_json" python3 - <<'PY'
import json
import os
from urllib.parse import urlparse

try:
    payload = json.loads(os.environ["METADATA_JSON"])
except json.JSONDecodeError as exc:
    raise SystemExit(f"Grok Bot download API returned invalid JSON: {exc}") from exc

download_url = payload.get("downloadUrl")
version = payload.get("version")
commit_sha = payload.get("commitSha", "")

for name, value in {
    "downloadUrl": download_url,
    "version": version,
    "commitSha": commit_sha,
}.items():
    if value is not None and not isinstance(value, str):
        raise SystemExit(f"Grok Bot download API field {name} must be a string")

if not download_url:
    raise SystemExit("Grok Bot download API response did not include downloadUrl")
if not version:
    raise SystemExit("Grok Bot download API response did not include version")

parsed = urlparse(download_url)
allowed_hosts = {
    "cursor.com",
    "www.cursor.com",
    "downloads.cursor.com",
    "api2.cursor.sh",
}
if parsed.scheme != "https" or parsed.netloc not in allowed_hosts:
    raise SystemExit(f"Refusing unexpected Grok Bot download host: {parsed.netloc or '<empty>'}")

values = [download_url, version, commit_sha]
if any(any(ord(char) < 32 for char in value) for value in values):
    raise SystemExit("Grok Bot download API response contained control characters")

print(download_url)
print(version)
print(commit_sha)
PY
}

download_to_file() {
  local url="$1"
  local destination="$2"
  curl \
    --fail \
    --location \
    --silent \
    --show-error \
    --retry 3 \
    --retry-delay 2 \
    --connect-timeout 20 \
    --max-time 900 \
    --proto '=https' \
    --proto-redir '=https' \
    --output "$destination" \
    "$url"
}

validate_appimage() {
  local file_path="$1"
  local magic
  [[ -s "$file_path" ]] || die "Downloaded AppImage is empty"
  magic=$(head -c 4 "$file_path" | od -An -tx1 | tr -d '[:space:]')
  [[ "$magic" == "7f454c46" ]] || die "Downloaded file is not an ELF/AppImage"
}

validate_icon() {
  local file_path="$1"
  python3 - "$file_path" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = path.read_bytes()
if not data:
    raise SystemExit("Downloaded icon is empty")

is_ico = data.startswith(b"\x00\x00\x01\x00")
is_png = data.startswith(b"\x89PNG\r\n\x1a\n")
is_svg = data.lstrip().startswith((b"<svg", b"<?xml"))
if not (is_ico or is_png or is_svg):
    raise SystemExit("Downloaded icon is not ICO, PNG, or SVG")
PY
}

write_metadata() {
  local destination="$1"
  local version="$2"
  local commit_sha="$3"
  local download_url="$4"
  local installed_at
  installed_at=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
  {
    printf 'VERSION=%q\n' "$version"
    printf 'COMMIT_SHA=%q\n' "$commit_sha"
    printf 'DOWNLOAD_URL=%q\n' "$download_url"
    printf 'INSTALLED_AT=%q\n' "$installed_at"
  } >"$destination"
}

write_desktop_entry() {
  local destination="$1"
  {
    printf '[Desktop Entry]\n'
    printf 'Type=Application\n'
    printf 'Name=%s\n' "$APP_DISPLAY_NAME"
    printf 'Comment=AI code editor\n'
    printf 'Exec=%s %%F\n' "$appimage_path"
    printf 'Icon=%s\n' "$icon_path"
    printf 'Terminal=false\n'
    printf 'StartupNotify=true\n'
    printf 'StartupWMClass=Grok Bot\n'
    printf 'Categories=Development;IDE;\n'
    printf 'MimeType=text/plain;inode/directory;\n'
  } >"$destination"
}

install_appimage_only() {
  local release_url="$1"
  local version="$2"
  local commit_sha="$3"
  mkdir -p -- "$install_dir"
  tmp_appimage=$(mktemp "$install_dir/grok-bot.AppImage.XXXXXX")
  tmp_metadata=$(mktemp "$install_dir/version.env.XXXXXX")
  printf 'Downloading Grok Bot %s...\n' "$version"
  download_to_file "$release_url" "$tmp_appimage"
  validate_appimage "$tmp_appimage"
  chmod 0755 "$tmp_appimage"
  write_metadata "$tmp_metadata" "$version" "$commit_sha" "$release_url"
  chmod 0644 "$tmp_metadata"
  mv -f -- "$tmp_appimage" "$appimage_path"
  mv -f -- "$tmp_metadata" "$metadata_path"
  tmp_appimage=""
  tmp_metadata=""
}

install_release() {
  local release_url="$1"
  local version="$2"
  local commit_sha="$3"
  if [[ "$appimage_only" == true ]]; then
    install_appimage_only "$release_url" "$version" "$commit_sha"
    printf 'Installed Grok Bot %s -> %s\n' "$version" "$appimage_path"
    return 0
  fi
  mkdir -p -- "$install_dir" "$(dirname "$desktop_file")"
  tmp_appimage=$(mktemp "$install_dir/grok-bot.AppImage.XXXXXX")
  tmp_icon=$(mktemp "$install_dir/grok-bot.ico.XXXXXX")
  tmp_metadata=$(mktemp "$install_dir/version.env.XXXXXX")
  tmp_desktop=$(mktemp "$(dirname "$desktop_file")/$APP_ID.XXXXXX.desktop")
  printf 'Downloading Grok Bot %s...\n' "$version"
  download_to_file "$release_url" "$tmp_appimage"
  validate_appimage "$tmp_appimage"
  chmod 0755 "$tmp_appimage"
  printf 'Downloading Grok Bot icon...\n'
  download_to_file "$icon_url" "$tmp_icon"
  validate_icon "$tmp_icon"
  chmod 0644 "$tmp_icon"
  write_metadata "$tmp_metadata" "$version" "$commit_sha" "$release_url"
  chmod 0644 "$tmp_metadata"
  write_desktop_entry "$tmp_desktop"
  chmod 0644 "$tmp_desktop"
  if command -v desktop-file-validate >/dev/null 2>&1; then
    desktop-file-validate "$tmp_desktop"
  fi
  mv -f -- "$tmp_appimage" "$appimage_path"
  mv -f -- "$tmp_icon" "$icon_path"
  mv -f -- "$tmp_metadata" "$metadata_path"
  mv -f -- "$tmp_desktop" "$desktop_file"
  tmp_appimage=""
  tmp_icon=""
  tmp_metadata=""
  tmp_desktop=""
  if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$(dirname "$desktop_file")" >/dev/null 2>&1 || true
  fi
  printf 'Installed Grok Bot %s -> %s\n' "$version" "$appimage_path"
}

resolve_release() {
  local release_api_url metadata_json
  local -a release_metadata
  if [[ -n "$direct_url" ]]; then
    [[ -n "$direct_version" ]] || die "--version is required with --url"
    release_metadata=("$direct_url" "$direct_version" "${direct_commit:-}")
    printf '%s\n' "${release_metadata[@]}"
    return 0
  fi
  release_api_url=$(build_api_url)
  printf 'Checking Grok Bot release metadata (%s)...\n' "$release_track" >&2
  metadata_json=$(curl \
    --fail \
    --location \
    --silent \
    --show-error \
    --retry 3 \
    --retry-delay 2 \
    --connect-timeout 20 \
    --max-time 60 \
    --proto '=https' \
    --proto-redir '=https' \
    "$release_api_url")
  mapfile -t release_metadata < <(fetch_release_metadata "$metadata_json")
  ((${#release_metadata[@]} >= 2)) || die "Grok Bot metadata parsing failed"
  printf '%s\n' "${release_metadata[@]}"
}

main() {
  while (($#)); do
    case "$1" in
      --track)
        (($# >= 2)) || die "--track requires a value"
        release_track="$2"
        shift 2
        ;;
      --url)
        (($# >= 2)) || die "--url requires a value"
        direct_url="$2"
        shift 2
        ;;
      --version)
        (($# >= 2)) || die "--version requires a value"
        direct_version="$2"
        shift 2
        ;;
      --commit)
        (($# >= 2)) || die "--commit requires a value"
        direct_commit="$2"
        shift 2
        ;;
      --app-name)
        (($# >= 2)) || die "--app-name requires a value"
        app_name="$2"
        shift 2
        ;;
      --install-dir)
        (($# >= 2)) || die "--install-dir requires a value"
        install_dir="$2"
        appimage_path="$install_dir/grok-bot.AppImage"
        icon_path="$install_dir/grok-bot.ico"
        metadata_path="$install_dir/version.env"
        shift 2
        ;;
      --appimage-only)
        appimage_only=true
        shift
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

  need_cmd curl
  need_cmd python3
  need_cmd head
  need_cmd od
  need_cmd tr
  need_cmd date
  need_cmd mktemp

  if [[ -n "$direct_url" ]]; then
    validate_https_url "$direct_url" "--url"
  else
    validate_https_url "$api_url" "GROKBOT_API_URL"
    validate_token "$platform" "GROKBOT_PLATFORM"
    validate_token "$release_track" "GROKBOT_RELEASE_TRACK"
  fi

  if [[ "$appimage_only" != true ]]; then
    validate_https_url "$icon_url" "GROKBOT_ICON_URL"
  fi
  [[ -z "$app_name" ]] || validate_token "$app_name" "GROKBOT_APP_NAME"

  local -a release_metadata
  mapfile -t release_metadata < <(resolve_release)
  install_release "${release_metadata[0]}" "${release_metadata[1]}" "${release_metadata[2]:-}"
  if [[ -n "${release_metadata[2]:-}" ]]; then
    printf 'Commit: %s\n' "${release_metadata[2]}"
  fi
  printf 'Metadata -> %s\n' "$metadata_path"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
