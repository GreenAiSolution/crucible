#!/usr/bin/env bash
# Start the CRUCIBLE desk.
set -euo pipefail
cd "$(dirname "$0")"
exec python3 -m crucible.server "${1:-8122}"
