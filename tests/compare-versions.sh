#!/bin/bash
# Compare claude-usage output between git HEAD and working copy
# Usage: ./compare-versions.sh [widths]
#
# Extracts HEAD version to temp file, runs both at various widths/subcommands,
# diffs output (ANSI stripped). Any differences indicate working copy changed behavior.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TOOL="$SCRIPT_DIR/claude-usage"
WIDTHS="${1:-69 80 86}"
SUBCOMMANDS="default hourly daily weekly"

# Find git root and determine relative path to tool
GIT_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null)"
if [ -z "$GIT_ROOT" ]; then
    echo "Error: Not in a git repository."
    exit 1
fi
TOOL_REL_PATH="${TOOL#$GIT_ROOT/}"

# Extract HEAD version to temp file
HEAD_TOOL=$(mktemp)
trap "rm -f '$HEAD_TOOL'" EXIT

cd "$GIT_ROOT"
if ! git show "HEAD:$TOOL_REL_PATH" > "$HEAD_TOOL" 2>/dev/null; then
    echo "Error: Cannot extract HEAD version of '$TOOL_REL_PATH'."
    echo "Is this file committed to git?"
    exit 1
fi
chmod +x "$HEAD_TOOL"

strip_ansi() {
    sed 's/\x1b\[[0-9;]*m//g'
}

DIFF_COUNT=0
TOTAL_TESTS=0

for W in $WIDTHS; do
    for SUB in $SUBCOMMANDS; do
        ((TOTAL_TESTS++)) || true
        printf "%-20s" "W=$W $SUB:"

        # Run HEAD version
        HEAD_OUT=$(COLUMNS=$W "$HEAD_TOOL" $SUB 2>/dev/null | strip_ansi || true)

        # Run working version
        WORK_OUT=$(COLUMNS=$W "$TOOL" $SUB 2>/dev/null | strip_ansi || true)

        # Compare
        if [ "$HEAD_OUT" != "$WORK_OUT" ]; then
            echo "DIFF"
            echo "--- HEAD"
            echo "+++ WORKING"
            diff <(echo "$HEAD_OUT") <(echo "$WORK_OUT") || true
            echo
            ((DIFF_COUNT++)) || true
        else
            echo "OK"
        fi
    done
done

echo
echo "=========================================="
if [ $DIFF_COUNT -gt 0 ]; then
    echo "RESULT: $DIFF_COUNT/$TOTAL_TESTS test(s) differ from HEAD"
    echo "Review diffs above to ensure changes are intentional."
    exit 1
else
    echo "RESULT: All $TOTAL_TESTS tests match HEAD"
    exit 0
fi
