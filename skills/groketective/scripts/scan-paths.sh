#!/usr/bin/env bash
# scan-paths.sh — inventory ~/.grokbot and ~/.config/Grok Bot (no secret values)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/_lib.sh"

[[ "${1:-}" == "--help" || "${1:-}" == "-h" ]] && {
  sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
  exit 0
}

emit_header "scan-paths.sh"

cfg="$(grokbot_config_root)"
data="$(grokbot_data_root)"
pers="$(persistence_root)"

path_stat_line "config_root" "$cfg"
path_stat_line "data_root" "$data"
path_stat_line "persistence_root" "$pers"
path_stat_line "settings_json" "${data}/settings.json"
path_stat_line "session_marker" "${cfg}/sand-session-marker.json"
path_stat_line "gateway_descriptor" "${cfg}/gateway-descriptor.json"
path_stat_line "window_state" "${cfg}/window-state.json"
path_stat_line "statsig_bootstrap" "${cfg}/sand-statsig-bootstrap.json"
path_stat_line "local_exec_daemon_json" "${data}/local-exec-daemon.json"
path_stat_line "local_exec_supervisor" "${data}/local-exec-supervisor.json"
path_stat_line "local_exec_log" "${data}/local-exec-daemon.log"

if [[ -d "$pers" ]]; then
  kv "persistence_blob_count" "$(find "$pers" -maxdepth 1 -type f -name '*.blob' 2>/dev/null | wc -l | tr -d ' ')"
fi

if [[ -f "${data}/settings.json" ]]; then
  echo "settings_redacted<<"
  redact_json_file "${data}/settings.json"
  echo ">>"
fi

if [[ -f "${cfg}/sand-session-marker.json" ]]; then
  echo "session_marker<<"
  redact_json_file "${cfg}/sand-session-marker.json"
  echo ">>"
fi

if [[ -f "${data}/local-exec-daemon.json" ]]; then
  echo "local_exec_daemon<<"
  redact_json_file "${data}/local-exec-daemon.json"
  echo ">>"
fi

# Presence-only for credential-bearing files
for secretish in \
  "${data}/local-exec-daemon-connection.json" \
  "${data}/local-exec-daemon-credential.json" \
  "${cfg}/sand-secrets.json" \
  "${cfg}/gateway-descriptor.json"
do
  base="$(basename "$secretish")"
  if [[ -f "$secretish" ]]; then
    kv "${base//./_}_present" "true"
    kv "${base//./_}_size" "$(human_bytes "$(stat -c '%s' "$secretish")")"
  else
    kv "${base//./_}_present" "false"
  fi
done
