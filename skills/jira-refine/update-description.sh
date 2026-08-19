#!/usr/bin/env bash
# Replace a Jira issue description via REST API v2 (Jira Server/DC, Bearer PAT).
#
# Usage: update-description.sh PROJ-123 /path/to/description.txt
#
# Reads JIRA_URL and JIRA_PERSONAL_TOKEN from the environment.
# Body file must be UTF-8, Jira wiki markup.
#
# A description update overwrites what was there. The current description is
# saved to a backup file first and its path is printed; the update is aborted if
# the backup cannot be written.
set -euo pipefail

KEY="${1:?usage: update-description.sh <ISSUE-KEY> <body-file>}"
BODY_FILE="${2:?usage: update-description.sh <ISSUE-KEY> <body-file>}"

[ -f "$BODY_FILE" ] || { echo "body file not found: $BODY_FILE" >&2; exit 1; }

# Git Bash's curl understands MSYS paths (/tmp/...), but a Windows Python on
# PATH does not — it resolves /tmp against the current drive root. Hand Python
# native paths via cygpath so both tools agree on which file is meant.
winpath() { cygpath -m "$1" 2>/dev/null || echo "$1"; }

BASE="${JIRA_URL:?set JIRA_URL, e.g. https://jira.example.com}"
BASE="${BASE%/}"
: "${JIRA_PERSONAL_TOKEN:?set JIRA_PERSONAL_TOKEN to a Jira personal access token}"

PAYLOAD="$(mktemp)"
RESP="$(mktemp)"
trap 'rm -f "$PAYLOAD" "$RESP"' EXIT

# The token goes in via --config on stdin, never as an argument: argv is visible
# to every other user on the machine through ps.
#
# curl's config parser needs the value quoted (unquoted, it stops at the colon in
# "Authorization:"), and inside quotes it reads \ and " as escapes — so escape
# those two first or a token containing either is silently mangled into a 401.
TOK=${JIRA_PERSONAL_TOKEN//\\/\\\\}
TOK=${TOK//\"/\\\"}
auth_curl() {
  curl -s -m 30 "$@" --config - <<CFG
header = "Authorization: Bearer ${TOK}"
CFG
}

# 1. Back up the current description before overwriting it.
BACKUP="${TMPDIR:-/tmp}/jira-$KEY-description-$(date +%Y%m%d-%H%M%S).txt"
HTTP=$(auth_curl -o "$RESP" -w '%{http_code}' "$BASE/rest/api/2/issue/$KEY?fields=description") || {
  echo "curl failed (exit $?) reaching $BASE — check JIRA_URL, VPN and TLS" >&2
  exit 1
}
if [ "$HTTP" != "200" ]; then
  echo "FAILED to read $KEY, HTTP=$HTTP" >&2
  cat "$RESP" >&2
  exit 1
fi
python - "$(winpath "$RESP")" "$(winpath "$BACKUP")" <<'PY'
import io, json, sys
d = json.load(io.open(sys.argv[1], encoding='utf-8'))['fields'].get('description') or ''
io.open(sys.argv[2], 'w', encoding='utf-8').write(d)
PY
echo "backup: $BACKUP"

# 2. Write the new description.
python - "$(winpath "$BODY_FILE")" "$(winpath "$PAYLOAD")" <<'PY'
import io, json, sys
body = io.open(sys.argv[1], encoding='utf-8').read()
io.open(sys.argv[2], 'w', encoding='utf-8').write(
    json.dumps({'fields': {'description': body}}))
PY

HTTP=$(auth_curl -o "$RESP" -w '%{http_code}' \
  -X PUT "$BASE/rest/api/2/issue/$KEY" \
  -H "Content-Type: application/json; charset=utf-8" \
  --data-binary "@$PAYLOAD") || {
  echo "curl failed (exit $?) reaching $BASE — check JIRA_URL, VPN and TLS" >&2
  exit 1
}

# A successful issue update returns 204 with an empty body.
if [ "$HTTP" = "204" ]; then
  echo "OK  $BASE/browse/$KEY  (description updated)"
else
  echo "FAILED HTTP=$HTTP" >&2
  cat "$RESP" >&2
  echo "description unchanged — previous text is still in $BACKUP" >&2
  exit 1
fi
