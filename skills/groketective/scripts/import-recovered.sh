#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/_lib.sh
source "${SCRIPT_DIR}/_lib.sh"

emit_header "import-recovered.sh"

PERSISTENCE_ROOT="$(persistence_root)"
ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --persistence-root)
      PERSISTENCE_ROOT="$2"
      shift 2
      ;;
    *)
      ARGS+=("$1")
      shift
      ;;
  esac
done

exec python3 "${SCRIPT_DIR}/import_recovered.py" --persistence-root "${PERSISTENCE_ROOT}" "${ARGS[@]}"
