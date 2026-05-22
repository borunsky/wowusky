#!/usr/bin/env bash
# Run wowusky directly from this checkout without installing it.
set -euo pipefail
cd "$(dirname "$0")"
PYTHONPATH=. exec python3 -m wowusky "$@"
