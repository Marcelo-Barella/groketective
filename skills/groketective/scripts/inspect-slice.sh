#!/usr/bin/env bash
# inspect-slice.sh — read one persistence slice (roster, transcript, ui-layout, …)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/_lib.sh"

ROOT=""
KIND=""
AGENT=""
KEY_SUB=""
MAX_CHARS=4000
RAW=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --root) ROOT="$2"; shift 2 ;;
    --kind) KIND="$2"; shift 2 ;;
    --agent-id) AGENT="$2"; shift 2 ;;
    --key-substr) KEY_SUB="$2"; shift 2 ;;
    --max-chars) MAX_CHARS="$2"; shift 2 ;;
    --raw) RAW=true; shift ;;
    -h|--help)
      echo "Usage: inspect-slice.sh (--agent-id UUID | --kind KIND | --key-substr STR) [--root DIR] [--max-chars N] [--raw]"
      exit 0
      ;;
    *) die "unknown arg: $1" ;;
  esac
done

ROOT="${ROOT:-$(persistence_root)}"
[[ -n "$KIND" || -n "$AGENT" || -n "$KEY_SUB" ]] || die "pass --agent-id, --kind, or --key-substr"
require_cmd python3

emit_header "inspect-slice.sh"
kv "root" "$ROOT"

args=( "${SCRIPT_DIR}/slice_keys.py" read --root "$ROOT" --max-chars "$MAX_CHARS" )
[[ -n "$KIND" ]] && args+=( --kind "$KIND" )
[[ -n "$AGENT" ]] && args+=( --agent-id "$AGENT" )
[[ -n "$KEY_SUB" ]] && args+=( --key-substr "$KEY_SUB" )
[[ "$RAW" == true ]] && args+=( --raw )

python3 "${args[@]}"
