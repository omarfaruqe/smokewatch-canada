#!/usr/bin/env bash
# Build the API image for the server's architecture on this machine and package it, so the
# server only has to `docker load` it (no build load on the server).
#   scripts/ship_image.sh            -> deploy/snapshot/smokewatch-api.tar.gz (linux/amd64)
#   PLATFORM=linux/arm64 scripts/ship_image.sh
set -euo pipefail
cd "$(dirname "$0")/.."
PLATFORM="${PLATFORM:-linux/amd64}"
mkdir -p deploy/snapshot
docker buildx build --platform "$PLATFORM" -f deploy/Dockerfile -t smokewatch-api:latest --load .
docker save smokewatch-api:latest | gzip -1 > deploy/snapshot/smokewatch-api.tar.gz
ls -lh deploy/snapshot/smokewatch-api.tar.gz
