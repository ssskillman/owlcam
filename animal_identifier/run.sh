#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
exec uv run uvicorn animal_identifier.server:app --host 127.0.0.1 --port "${ANIMAL_ID_PORT:-8767}"
