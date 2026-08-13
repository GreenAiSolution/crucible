#!/usr/bin/env bash
# Rebuild the leaderboard and serve it on 8121.
set -euo pipefail
cd "$(dirname "$0")"
python3 -m crucible.cli leaderboard
echo "CRUCIBLE leaderboard -> http://localhost:8121"
exec python3 -m http.server 8121 --directory leaderboard
