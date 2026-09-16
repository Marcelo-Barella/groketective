#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/_lib.sh"

A="" B=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --a) A="$2"; shift 2 ;;
    --b) B="$2"; shift 2 ;;
    -h|--help) echo "Usage: compare-dirs.sh --a DIR --b DIR"; exit 0 ;;
    *) die "unknown arg: $1" ;;
  esac
done

[[ -d "$A" && -d "$B" ]] || die "both --a and --b must be directories"

emit_header "compare-dirs.sh"
kv "a" "$A"
kv "b" "$B"

comm -3 \
  <(find "$A" -maxdepth 1 -type f -printf '%f %s\n' 2>/dev/null | sort) \
  <(find "$B" -maxdepth 1 -type f -printf '%f %s\n' 2>/dev/null | sort) \
  | head -n "${TRUNCATE_MAX}" | sed 's/^/diff_line=/' || true
