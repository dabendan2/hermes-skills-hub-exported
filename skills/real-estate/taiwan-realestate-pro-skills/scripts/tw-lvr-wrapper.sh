#!/bin/bash
# Dynamically locate the Playwright chrome-headless-shell binary
PLAYWRIGHT_SHELL=$(find ~/.cache/ms-playwright -name "chrome-headless-shell" 2>/dev/null | head -n 1)

if [ -z "$PLAYWRIGHT_SHELL" ]; then
    # Fallback to alternative paths under home directory
    PLAYWRIGHT_SHELL=$(find ~/ -name "chrome-headless-shell" -path "*/ms-playwright/*" 2>/dev/null | head -n 1)
fi

if [ -n "$PLAYWRIGHT_SHELL" ]; then
    export LVR_HEADLESS_SHELL="$PLAYWRIGHT_SHELL"
fi

# Execute the actual tw-lvr CLI with all original arguments
exec tw-lvr "$@"
