#!/usr/bin/env bash
# inspect-daemon.sh — local-exec daemon/supervisor status with secrets redacted
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/_lib.sh"

[[ "${1:-}" == "--help" || "${1:-}" == "-h" ]] && {
  echo "Usage: inspect-daemon.sh"
  exit 0
}

emit_header "inspect-daemon.sh"
data="$(grokbot_data_root)"
kv "data_root" "$data"

for f in settings.json local-exec-daemon.json local-exec-supervisor.json local-exec-daemon.log; do
  path_stat_line "${f//./_}" "${data}/${f}"
done

for f in local-exec-daemon-connection.json local-exec-daemon-credential.json; do
  p="${data}/${f}"
  if [[ -f "$p" ]]; then
    kv "${f//./_}_present" "true"
    kv "${f//./_}_size" "$(human_bytes "$(stat -c '%s' "$p")")"
    # Structure only: top-level keys, never values for secret fields
    require_cmd python3
    python3 - "$p" <<'PY'
import json, re, sys
path = sys.argv[1]
secret_re = re.compile(r"(token|credential|password|secret|encrypted|authorization|cookie|api[_-]?key)", re.I)
try:
    data = json.load(open(path, encoding="utf-8"))
except Exception as e:
    print(f"parse_error={e}")
    raise SystemExit(0)
if isinstance(data, dict):
    print("top_level_keys=" + ",".join(sorted(data.keys())))
    for k, v in data.items():
        if secret_re.search(k):
            print(f"{k}=<redacted>")
        elif isinstance(v, dict):
            print(f"{k}_keys=" + ",".join(sorted(v.keys())))
        elif isinstance(v, str) and ("http://" in v or "https://" in v):
            # host only
            from urllib.parse import urlparse
            u = urlparse(v)
            print(f"{k}_host={u.scheme}://{u.netloc}")
        elif isinstance(v, (int, float, bool)) or v is None:
            print(f"{k}={v}")
        else:
            print(f"{k}_type={type(v).__name__}")
PY
  else
    kv "${f//./_}_present" "false"
  fi
done

if [[ -f "${data}/local-exec-daemon.json" ]]; then
  echo "daemon_json<<"
  redact_json_file "${data}/local-exec-daemon.json"
  echo ">>"
fi

if [[ -f "${data}/local-exec-supervisor.json" ]]; then
  echo "supervisor_json<<"
  redact_json_file "${data}/local-exec-supervisor.json"
  echo ">>"
fi

if [[ -f "${data}/local-exec-daemon.log" ]]; then
  echo "daemon_log_tail<<"
  tail -n 40 "${data}/local-exec-daemon.log" || true
  echo ">>"
fi

# Alive check vs recorded pid
if [[ -f "${data}/local-exec-daemon.json" ]]; then
  pid="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("pid",""))' "${data}/local-exec-daemon.json" 2>/dev/null || true)"
  if [[ -n "${pid}" ]]; then
    if kill -0 "$pid" 2>/dev/null; then
      kv "daemon_pid_alive" "true"
    else
      kv "daemon_pid_alive" "false"
    fi
    kv "daemon_pid" "$pid"
  fi
fi
