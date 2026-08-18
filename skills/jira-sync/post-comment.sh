#!/usr/bin/env bash
# Post a comment to a Jira issue via REST API v2 (Jira Server/DC, Bearer PAT).
#
# Usage: post-comment.sh PROJ-123 /path/to/body.txt
#
# Reads JIRA_URL and JIRA_PERSONAL_TOKEN from the environment.
# JIRA_COMMENT_MAX caps the body length in characters (default 1000, 0 disables).
# Body file must be UTF-8, Markdown.
set -euo pipefail

KEY="${1:?usage: post-comment.sh <ISSUE-KEY> <body-file>}"
BODY_FILE="${2:?usage: post-comment.sh <ISSUE-KEY> <body-file>}"

[ -f "$BODY_FILE" ] || { echo "body file not found: $BODY_FILE" >&2; exit 1; }

# Git Bash's curl understands MSYS paths (/tmp/...), but a Windows Python on
# PATH does not — it resolves /tmp against the current drive root. Hand Python
# native paths via cygpath so both tools agree on which file is meant.
winpath() { cygpath -m "$1" 2>/dev/null || echo "$1"; }

BASE="${JIRA_URL:?set JIRA_URL, e.g. https://jira.example.com}"
BASE="${BASE%/}"
: "${JIRA_PERSONAL_TOKEN:?set JIRA_PERSONAL_TOKEN to a Jira personal access token}"

MAX="${JIRA_COMMENT_MAX:-1000}"
case "$MAX" in
  *[!0-9]*|"") echo "JIRA_COMMENT_MAX must be a number of characters (0 disables): $MAX" >&2; exit 1 ;;
esac

PAYLOAD="$(mktemp)"
RESP="$(mktemp)"
trap 'rm -f "$PAYLOAD" "$RESP"' EXIT
# characters, not bytes — a CJK summary is well under the cap by length and well
# over it by byte count
python - "$(winpath "$BODY_FILE")" "$(winpath "$PAYLOAD")" "$MAX" <<'PY'
import io, json, sys
body = io.open(sys.argv[1], encoding='utf-8').read()
limit = int(sys.argv[3] or 0)
if limit and len(body) > limit:
    # ASCII only: this goes to stderr, and a Windows console on a legacy code
    # page garbles or refuses anything else, hiding the real message
    sys.exit("comment is %d characters, limit is %d - shorten it or raise "
             "JIRA_COMMENT_MAX" % (len(body), limit))
io.open(sys.argv[2], 'w', encoding='utf-8').write(json.dumps({'body': body}))
PY

# The token goes in via --config on stdin, never as an argument: argv is visible
# to every other user on the machine through ps.
#
# curl's config parser needs the value quoted (unquoted, it stops at the colon in
# "Authorization:"), and inside quotes it reads \ and " as escapes — so escape
# those two first or a token containing either is silently mangled into a 401.
TOK=${JIRA_PERSONAL_TOKEN//\\/\\\\}
TOK=${TOK//\"/\\\"}
HTTP=$(curl -s -o "$RESP" -w '%{http_code}' -m 30 \
  -X POST "$BASE/rest/api/2/issue/$KEY/comment" \
  -H "Content-Type: application/json; charset=utf-8" \
  --data-binary "@$PAYLOAD" \
  --config - <<CFG
header = "Authorization: Bearer ${TOK}"
CFG
) || {
  # curl itself failed (DNS, TLS, timeout) — without this, set -e would abort silently
  echo "curl failed (exit $?) reaching $BASE — check JIRA_URL, VPN and TLS" >&2
  exit 1
}

if [ "$HTTP" = "201" ]; then
  ID=$(python -c "import io,json,sys;print(json.load(io.open(sys.argv[1],encoding='utf-8'))['id'])" "$(winpath "$RESP")")
  echo "OK  $BASE/browse/$KEY  (comment id $ID)"
else
  echo "FAILED HTTP=$HTTP" >&2
  cat "$RESP" >&2
  exit 1
fi
