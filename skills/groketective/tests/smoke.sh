#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPTS="${ROOT}/scripts"
FIXTURES="${ROOT}/tests/fixtures"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

mkdir -p "${TMP}/pers" "${TMP}/da" "${TMP}/db"
echo x > "${TMP}/da/a.txt"

# Fixture slice
python3 "${SCRIPTS}/slice_keys.py" encode 'sand.client.slice.ui-layout' > "${TMP}/stem.txt"
STEM="$(cat "${TMP}/stem.txt")"
printf '%s\n' '{"schemaVersion":1,"value":{"ok":true}}' > "${TMP}/pers/${STEM}.blob"

out="${TMP}/list.out"
"${SCRIPTS}/list-persistence.sh" --root "${TMP}/pers" >"$out"
grep -q 'kind=ui-layout' "$out"
grep -q 'sand.client.slice.ui-layout' "$out"

out="${TMP}/inspect.out"
"${SCRIPTS}/inspect-slice.sh" --root "${TMP}/pers" --kind ui-layout >"$out"
grep -q 'schemaVersion' "$out"

out="${TMP}/compare.out"
"${SCRIPTS}/compare-dirs.sh" --a "${TMP}/da" --b "${TMP}/db" >"$out"
grep -q '^diff_line=' "$out"

"${SCRIPTS}/locate-grokbot.sh" >/dev/null
"${SCRIPTS}/scan-paths.sh" >/dev/null

python3 "${ROOT}/tests/test_import_recovered.py" >/dev/null

printf '%s\n' '{"token":"SUPER_SECRET_TOKEN_VALUE","pid":1}' > "${TMP}/secret.json"
source "${SCRIPTS}/_lib.sh"
out="${TMP}/redact.out"
redact_json_file "${TMP}/secret.json" >"$out"
grep -q '<redacted>' "$out"
grep -qv 'SUPER_SECRET_TOKEN_VALUE' "$out"

echo "smoke: OK"
