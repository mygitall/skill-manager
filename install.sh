#!/usr/bin/env bash
# skill-manager install script
# Run: bash install.sh
set -euo pipefail

SKILL_NAME="skill-manager"
DEST="$HOME/.agents/skills/$SKILL_NAME"

echo "Installing $SKILL_NAME to $DEST ..."

if [ -d "$DEST" ]; then
    echo "Existing installation found. Backing up..."
    BACKUP="$HOME/.agents/skills/.backups/${SKILL_NAME}-$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$(dirname "$BACKUP")"
    cp -r "$DEST" "$BACKUP"
    echo "Backup: $BACKUP"
    rm -rf "$DEST"
fi

mkdir -p "$(dirname "$DEST")"
cp -r "$(dirname "$0")" "$DEST"
chmod +x "$DEST/scripts/skillctl.py"
chmod +x "$DEST/install.sh"

echo ""
echo "Done! Verify with:"
echo "  python3 $DEST/scripts/skillctl.py --version"
echo "  python3 $DEST/scripts/skillctl.py list"
echo ""
echo "In Codex, use: \$skill-manager list all skills"
