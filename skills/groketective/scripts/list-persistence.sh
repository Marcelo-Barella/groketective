#!/usr/bin/env bash
# list-persistence.sh — decode sand-client-persistence blob keys
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/_lib.sh"

ROOT=""
KIND=""
AGENT=""
JSON=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --root) ROOT="$2"; shift 2 ;;
    --kind) KIND="$2"; shift 2 ;;
    --agent-id) AGENT="$2"; shift 2 ;;
    --json) JSON=true; shift ;;
    -h|--help)
      echo "Usage: list-persistence.sh [--root DIR] [--kind KIND] [--agent-id UUID] [--json]"
      exit 0
      ;;
    *) die "unknown arg: $1" ;;
  esac
done

ROOT="${ROOT:-$(persistence_root)}"
require_cmd python3

emit_header "list-persistence.sh"
kv "root" "$ROOT"

args=( "${SCRIPT_DIR}/slice_keys.py" list --root "$ROOT" )
[[ -n "$KIND" ]] && args+=( --kind "$KIND" )
[[ -n "$AGENT" ]] && args+=( --agent-id "$AGENT" )
[[ "$JSON" == true ]] && args+=( --json )

python3 "${args[@]}"
