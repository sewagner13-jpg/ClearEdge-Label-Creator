#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_FILE="$REPO_DIR/desktop/ClearEdge-Label-Creator.desktop"
TARGET_DIR="$HOME/Desktop"
TARGET_FILE="$TARGET_DIR/ClearEdge-Label-Creator.desktop"

mkdir -p "$TARGET_DIR"
cp "$SOURCE_FILE" "$TARGET_FILE"
chmod +x "$TARGET_FILE"

echo "✅ Desktop icon installed at: $TARGET_FILE"
echo "If your desktop requires trusted launchers, right-click and allow launching."
