#!/usr/bin/env bash
# shellcheck disable=SC2034
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"

emit_header() {
  local script="$1"
  local note="${2:-}"
  echo "script=${script}"
  echo "timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  if [[ -n "$note" ]]; then
    echo "note=${note}"
  fi
}

kv() { printf '%s=%s\n' "$1" "$2"; }

die() {
  echo "error: $*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"
}

human_bytes() {
  local n="$1"
  if (( n < 1024 )); then echo "${n}B"; return; fi
  if (( n < 1048576 )); then echo "$(( n / 1024 ))KB"; return; fi
  echo "$(( n / 1048576 ))MB"
}

path_stat_line() {
  local label="$1"
  local p="$2"
  if [[ -e "$p" ]]; then
    local sz mt
    sz=$(stat -c '%s' "$p" 2>/dev/null || stat -f '%z' "$p")
    mt=$(stat -c '%y' "$p" 2>/dev/null || stat -f '%Sm' "$p")
    kv "${label}_exists" "true"
    kv "${label}_path" "$p"
    kv "${label}_size" "$(human_bytes "$sz")"
    kv "${label}_mtime" "$mt"
  else
    kv "${label}_exists" "false"
    kv "${label}_path" "$p"
  fi
}

grokbot_install_root() {
  echo "${GROKBOT_INSTALL_ROOT:-/opt/Grok Bot}"
}

grokbot_config_root() {
  local home sys
  home="${HOME}"
  sys="$(uname -s)"
  case "$sys" in
    Darwin) echo "${home}/Library/Application Support/Grok Bot" ;;
    *) echo "${home}/.config/Grok Bot" ;;
  esac
}

grokbot_data_root() {
  echo "${HOME}/.grokbot"
}

persistence_root() {
  echo "$(grokbot_config_root)/sand-client-persistence"
}

asar_path() {
  echo "$(grokbot_install_root)/resources/app.asar"
}

binary_path() {
  local root
  root="$(grokbot_install_root)"
  if [[ -x "${root}/grok-bot" ]]; then
    echo "${root}/grok-bot"
  else
    echo "${root}/sand"
  fi
}

normalize_theme() {
  local raw="${1:-}"
  raw="$(echo "$raw" | tr '[:upper:]' '[:lower:]' | tr ' _' '-')"
  raw="$(echo "$raw" | sed -E 's/[^a-z0-9-]+//g; s/-+/-/g; s/^-|-$//g')"
  if [[ -z "$raw" ]]; then raw="general-scan"; fi
  echo "$raw"
}

TRUNCATE_MAX="${TRUNCATE_MAX:-20}"
SECRET_KEY_RE='(token|credential|password|secret|encrypted|authorization|cookie|api[_-]?key)'

# @electron/asar extract-file writes <basename> into the current directory only.
extract_asar_file() {
  local asar="$1"
  local inner="$2"
  local dest="$3"
  local base tmpdir
  require_cmd npx
  base="$(basename "$inner")"
  tmpdir="$(mktemp -d)"
  (
    cd "$tmpdir"
    npx --yes @electron/asar extract-file "$asar" "$inner" >/dev/null
  )
  if [[ ! -f "${tmpdir}/${base}" ]]; then
    rm -rf "$tmpdir"
    return 1
  fi
  mkdir -p "$(dirname "$dest")"
  mv "${tmpdir}/${base}" "$dest"
  rm -rf "$tmpdir"
  return 0
}

redact_json_file() {
  local path="$1"
  require_cmd python3
  python3 - "$path" <<'PY'
import json, re, sys
path = sys.argv[1]
secret_re = re.compile(r"(token|credential|password|secret|encrypted|authorization|cookie|api[_-]?key)", re.I)

def scrub(obj):
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if secret_re.search(str(k)):
                out[k] = "<redacted>"
            else:
                out[k] = scrub(v)
        return out
    if isinstance(obj, list):
        return [scrub(x) for x in obj]
    if isinstance(obj, str) and len(obj) > 24 and secret_re.search(obj):
        return "<redacted>"
    return obj

try:
    data = json.loads(open(path, "r", encoding="utf-8").read())
except Exception as e:
    print(f"json_error={e}")
    sys.exit(0)
print(json.dumps(scrub(data), indent=2, ensure_ascii=False))
PY
}
