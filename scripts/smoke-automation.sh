#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="${ROOT}/scripts${PYTHONPATH:+:${PYTHONPATH}}"
python3 "$ROOT/skills/groketective/tests/test_catalog_feature_flags.py"
python3 "$ROOT/skills/groketective/tests/test_diff_build_extracts.py"
python3 "$ROOT/skills/groketective/tests/test_notion_flag_gaps.py"
python3 "$ROOT/skills/groketective/tests/test_grokbot_dogfood_feed.py"
echo "smoke-automation=ok"
