#!/usr/bin/env bash
# wowusky — local install script for Arch / CachyOS
# Installs into the user's $HOME (no root needed, no pip needed).
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_NAME="wowusky"

BIN_DIR="$HOME/.local/bin"
APP_DIR="$HOME/.local/share/$APP_NAME"
DESKTOP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
ICON_BASE="$HOME/.local/share/icons/hicolor"

echo
echo "  wowusky — installer"
echo "  ────────────────────────────────────────"
echo

# Cleanup old elvui-updater / older wowusky layouts
for legacy in \
    "$HOME/.local/share/elvui-updater" \
    "$HOME/.local/bin/elvui-updater" \
    "$HOME/.local/share/applications/elvui-updater.desktop"
do
    if [ -e "$legacy" ]; then
        echo "  removing legacy: $legacy"
        rm -rf "$legacy"
    fi
done

mkdir -p "$BIN_DIR" "$APP_DIR" "$DESKTOP_DIR" "$ICON_DIR"

# Clean any previous install in APP_DIR but keep the user's runtime
# data (config.json, profiles.json, installed/, wago.json, …).
echo "  installing files → $APP_DIR"
rm -rf "$APP_DIR/wowusky" "$APP_DIR/pyproject.toml" "$APP_DIR/README.md" \
       "$APP_DIR/LICENSE" "$APP_DIR/CHANGELOG.md"

# IMPORTANT: copy the wowusky package as a SUBDIRECTORY of APP_DIR.
# This way the launcher can put APP_DIR on PYTHONPATH and Python will
# discover the `wowusky` package correctly.
#
# Layout after install:
#   ~/.local/share/wowusky/
#   ├── wowusky/              ← the actual Python package
#   │   ├── __init__.py
#   │   ├── catalog/
#   │   ├── core/
#   │   └── …
#   ├── pyproject.toml        (informational)
#   ├── README.md
#   └── LICENSE
cp -r "$SCRIPT_DIR/wowusky"        "$APP_DIR/wowusky"
cp    "$SCRIPT_DIR/pyproject.toml" "$APP_DIR/pyproject.toml" 2>/dev/null || true
cp    "$SCRIPT_DIR/README.md"      "$APP_DIR/README.md"      2>/dev/null || true
cp    "$SCRIPT_DIR/LICENSE"        "$APP_DIR/LICENSE"        2>/dev/null || true
cp    "$SCRIPT_DIR/CHANGELOG.md"   "$APP_DIR/CHANGELOG.md"   2>/dev/null || true

# Remove any __pycache__ that snuck in via copy
find "$APP_DIR/wowusky" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# Launcher script
cat > "$BIN_DIR/wowusky" << EOF
#!/usr/bin/env bash
# wowusky launcher — sets PYTHONPATH so the wowusky package is found.
PYTHONPATH="$APP_DIR" exec python3 -m wowusky "\$@"
EOF
chmod +x "$BIN_DIR/wowusky"
echo "  ✓ launcher: $BIN_DIR/wowusky"

# Desktop entry + icon
if [ -f "$SCRIPT_DIR/packaging/wowusky.desktop" ]; then
    install -Dm644 "$SCRIPT_DIR/packaging/wowusky.desktop" \
                   "$DESKTOP_DIR/wowusky.desktop"
    echo "  ✓ desktop entry installed"
fi
if [ -f "$SCRIPT_DIR/packaging/wowusky.svg" ]; then
    install -Dm644 "$SCRIPT_DIR/packaging/wowusky.svg" \
                   "$ICON_DIR/wowusky.svg"
    echo "  ✓ icon installed (svg)"
fi
# PNG fallbacks for icon themes that don't render SVG
for sz in 32 64 128 256 512; do
    SRC="$SCRIPT_DIR/packaging/wowusky-$sz.png"
    if [ -f "$SRC" ]; then
        install -Dm644 "$SRC" "$ICON_BASE/${sz}x${sz}/apps/wowusky.png"
    fi
done
echo "  ✓ icons installed (png 32–512)"

# Refresh desktop and icon caches if those tools are available
command -v update-desktop-database &>/dev/null && \
    update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
command -v gtk-update-icon-cache &>/dev/null && \
    gtk-update-icon-cache "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

# Sanity check: can Python actually find and import the package?
if PYTHONPATH="$APP_DIR" python3 -c "import wowusky; from wowusky.catalog import load_catalog; load_catalog()" 2>/dev/null; then
    echo "  ✓ import test passed"
else
    echo "  ✗ import test FAILED — please report this with:"
    echo "      PYTHONPATH=$APP_DIR python3 -c 'import wowusky'"
fi

# Quick smoke test: can Python actually import the installed package?
if PYTHONPATH="$APP_DIR" python3 -c "import wowusky; from wowusky.catalog import load_catalog" 2>/dev/null; then
    echo "  ✓ package imports cleanly"
else
    echo "  ✗ WARNING: package failed to import — check $APP_DIR layout"
    echo "    run for details: PYTHONPATH=\"$APP_DIR\" python3 -c 'import wowusky'"
fi

# PATH check
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo
    echo "  note: ~/.local/bin is not in your PATH."
    echo "  add to ~/.bashrc / ~/.zshrc:"
    echo '    export PATH="$HOME/.local/bin:$PATH"'
    echo "  or for fish:"
    echo "    fish_add_path ~/.local/bin"
fi

echo
echo "  installation complete."
echo "  run with: wowusky"
echo
