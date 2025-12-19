#!/bin/bash
# Helper script for testing claude-usage at various widths
# Edit this file to change test parameters

WIDTHS="${1:-69 74 80 81 86 97}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

for W in $WIDTHS; do
    echo "=== W=$W ==="
    COLUMNS=$W "$SCRIPT_DIR/claude-usage" 2>&1 | sed 's/\x1b\[[0-9;]*m//g' | while read line; do
        len=${#line}
        if [ $len -gt $W ]; then
            echo "OVERFLOW: $len chars (expected max $W)"
            printf '%s\n' "$line"
        fi
    done
    echo
done

echo "Done. Any lines above show overflows."
