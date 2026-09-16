#!/usr/bin/env bash
# locate-grokbot.sh — resolve Grok Bot install root, binary, app.asar, version
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/_lib.sh
source "${SCRIPT_DIR}/_lib.sh"

[[ "${1:-}" == "--help" || "${1:-}" == "-h" ]] && {
  sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
  exit 0
}

emit_header "locate-grokbot.sh"

sys="$(uname -s)"
kv "platform" "$sys"

case "$sys" in
  Linux) ;;
  Darwin)
    kv "probe_status" "partial"
    kv "probe_note" "macOS paths listed in reference.md; Linux is primary"
    ;;
  *)
    kv "probe_status" "skipped"
    kv "probe_note" "non-Linux install search not implemented in v1"
    ;;
esac

candidates=(
  "$(grokbot_install_root)"
  "/opt/Grok Bot"
  "/usr/share/grok-bot"
  "${HOME}/Applications/Grok Bot"
)

best=""
for root in "${candidates[@]}"; do
  [[ -d "$root" ]] || continue
  kv "candidate_install" "$root"
  if [[ -f "${root}/resources/app.asar" || -x "${root}/sand" || -x "${root}/grok-bot" ]]; then
    best="$root"
    break
  fi
done

if [[ -z "$best" ]]; then
  kv "INSTALL_ROOT" ""
  kv "install_status" "not_found"
  kv "APP_ASAR" ""
  kv "BINARY" ""
  exit 0
fi

export GROKBOT_INSTALL_ROOT="$best"
kv "INSTALL_ROOT" "$best"
kv "install_status" "found"

bin="$(binary_path)"
grok_bin="${best}/grok-bot"
asar="$(asar_path)"
path_stat_line "binary" "$bin"
path_stat_line "grok_bot_binary" "$grok_bin"
path_stat_line "app_asar" "$asar"
kv "BINARY" "$bin"
if [[ -x "$grok_bin" ]]; then
  kv "GROK_BOT_BINARY" "$grok_bin"
else
  kv "GROK_BOT_BINARY" ""
fi
kv "APP_ASAR" "$asar"

if [[ -f "$asar" ]] && command -v npx >/dev/null 2>&1; then
  tmp="$(mktemp)"
  if extract_asar_file "$asar" "package.json" "$tmp"; then
    ver="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("version","unknown"))' "$tmp" 2>/dev/null || echo unknown)"
    name="$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d.get("productName") or d.get("name","unknown"))' "$tmp" 2>/dev/null || echo unknown)"
    pkg="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("name","unknown"))' "$tmp" 2>/dev/null || echo unknown)"
    kv "grokbot_version" "$ver"
    kv "product_name" "$name"
    kv "package_name" "$pkg"
  else
    kv "grokbot_version" "unknown"
    kv "package_json_extract" "failed"
  fi
  rm -f "$tmp"
elif [[ -x "$bin" ]]; then
  kv "grokbot_version" "unknown"
fi

running_pids=""
for pat in '/opt/Grok Bot/sand' '/opt/Grok Bot/grok-bot' 'grok-bot'; do
  if [[ "$pat" == "grok-bot" ]]; then
    while IFS= read -r pid; do
      [[ -n "$pid" ]] && running_pids+="${pid},"
    done < <(pgrep -x grok-bot 2>/dev/null || true)
  else
    while IFS= read -r pid; do
      [[ -n "$pid" ]] && running_pids+="${pid},"
    done < <(pgrep -f "$pat" 2>/dev/null || true)
  fi
done
while IFS= read -r pid; do
  [[ -n "$pid" ]] && running_pids+="${pid},"
done < <(pgrep -x sand 2>/dev/null || true)
running_pids="$(echo "$running_pids" | sed 's/,$//')"
if [[ -n "$running_pids" ]]; then
  kv "process_running" "true"
  kv "process_pids" "$running_pids"
else
  kv "process_running" "false"
fi
