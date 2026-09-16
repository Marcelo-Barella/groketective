#!/usr/bin/env bash
# grep-asar.sh — pattern search in Grok Bot app.asar entrypoints (or whole archive)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/_lib.sh"

ASAR=""
PATTERN=""
BUILTIN=false
CACHE_DIR=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --asar) ASAR="$2"; shift 2 ;;
    --pattern) PATTERN="$2"; shift 2 ;;
    --builtin) BUILTIN=true; shift ;;
    --cache-dir) CACHE_DIR="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: grep-asar.sh [--asar PATH] [--pattern REGEX] [--builtin] [--cache-dir DIR]"
      exit 0
      ;;
    *) die "unknown arg: $1" ;;
  esac
done

if [[ -z "$ASAR" ]]; then
  ASAR="$("${SCRIPT_DIR}/locate-grokbot.sh" | awk -F= '/^APP_ASAR=/{print $2}' | tail -n 1)"
fi
[[ -f "$ASAR" ]] || die "app.asar not found (pass --asar PATH)"

emit_header "grep-asar.sh" "truncation_max=${TRUNCATE_MAX}"
kv "asar" "$ASAR"

patterns=()
if [[ "$BUILTIN" == true || -z "$PATTERN" ]]; then
  patterns=(
    sand.client.slice
    sand-client-persistence
    local-exec-daemon
    transcript.replicas
    roster.last-roster
    gateway-descriptor
    @anysphere/grok-bot
  )
else
  patterns=("$PATTERN")
fi

# Prefer entrypoint extracts when npx asar is available; else strings on whole asar
ENTRYPOINTS=(
  dist/electron-main/main.cjs
  dist/local-exec-daemon/main.cjs
  dist/host/host-main.cjs
  dist/electron-preload/preload.cjs
  package.json
)

CACHE_DIR="${CACHE_DIR:-$(mktemp -d)}"
kv "cache_dir" "$CACHE_DIR"
cleanup=false
if [[ "$CACHE_DIR" == /tmp/* ]]; then cleanup=true; fi
trap '[[ "$cleanup" == true ]] && rm -rf "$CACHE_DIR"' EXIT

extracted=false
if command -v npx >/dev/null 2>&1; then
  for ep in "${ENTRYPOINTS[@]}"; do
    out="${CACHE_DIR}/$(echo "$ep" | tr '/' '_')"
    if extract_asar_file "$ASAR" "$ep" "$out"; then
      kv "extracted" "$ep"
      extracted=true
    fi
  done
fi

search_targets=()
if [[ "$extracted" == true ]]; then
  while IFS= read -r f; do
    search_targets+=("$f")
  done < <(find "$CACHE_DIR" -type f 2>/dev/null)
else
  kv "extract_mode" "strings_fallback"
  search_targets=("$ASAR")
fi

for pat in "${patterns[@]}"; do
  kv "pattern" "$pat"
  total=0
  for f in "${search_targets[@]}"; do
    c="$(grep -a -c "$pat" "$f" 2>/dev/null || true)"
    c="${c:-0}"
    total=$((total + c))
    hits="$(grep -a -oE ".{0,40}${pat}.{0,40}" "$f" 2>/dev/null | head -n "${TRUNCATE_MAX}" || true)"
    if [[ -n "$hits" ]]; then
      kv "file" "$(basename "$f")"
      echo "$hits" | sed 's/^/snippet=/' || true
    fi
  done
  kv "hit_count" "$total"
done
