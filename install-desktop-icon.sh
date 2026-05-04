#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="$HOME/Desktop"
TARGET_FILE="$TARGET_DIR/ClearEdge-Label-Creator.desktop"

mkdir -p "$TARGET_DIR"
cat > "$TARGET_FILE" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=ClearEdge Label Creator
Comment=Start the ClearEdge Label Creator backend
Exec=bash -lc 'cd "$REPO_DIR" && ./run-local.sh'
Terminal=true
Icon=applications-science
Categories=Utility;Development;
StartupNotify=true
EOF
chmod +x "$TARGET_FILE"

echo "✅ Desktop icon installed at: $TARGET_FILE"
echo "If your desktop requires trusted launchers, right-click and allow launching."
