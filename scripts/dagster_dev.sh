#!/usr/bin/env bash
# Start Dagster (web UI on http://localhost:3000 plus the scheduler) for this project.
# Uses .dagster/ as DAGSTER_HOME and installs config/dagster.yaml there, so only one run
# executes at a time. An existing dagster.yaml without these settings is backed up first.
set -euo pipefail
cd "$(dirname "$0")/.."
export DAGSTER_HOME="$PWD/.dagster"
mkdir -p "$DAGSTER_HOME"
target="$DAGSTER_HOME/dagster.yaml"
if ! cmp -s config/dagster.yaml "$target"; then
    if [[ -s "$target" ]]; then
        cp "$target" "$target.bak.$(date +%Y%m%d%H%M%S)"
        echo "Backed up the previous $target"
    fi
    cp config/dagster.yaml "$target"
    echo "Installed config/dagster.yaml (one run at a time, telemetry off)"
fi
exec dagster dev "$@"
