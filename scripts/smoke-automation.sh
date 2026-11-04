#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 "$ROOT/skills/groketective/tests/test_catalog_feature_flags.py"
python3 "$ROOT/scripts/fetch-changelog-entries.py" \
  --pages 1 \
  --filter all \
  --output-dir "$(mktemp -d)" >/dev/null
echo "smoke-automation=ok"
