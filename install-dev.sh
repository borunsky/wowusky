#!/usr/bin/env bash
# One-shot: install into ~/.local and launch.
set -euo pipefail
cd "$(dirname "$0")"
chmod +x install.sh run-local.sh
./install.sh
exec wowusky
