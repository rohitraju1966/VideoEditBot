#!/usr/bin/env bash
# One-time setup for the vlog-editor skill (macOS, Apple Silicon).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
command -v ffmpeg >/dev/null || { echo "ffmpeg missing: brew install ffmpeg"; exit 1; }
VENV="$HOME/.vlog-editor-venv"
[ -d "$VENV" ] || python3 -m venv "$VENV"
"$VENV/bin/pip" install -q -r "$HERE/requirements.txt"
echo "python env: $VENV"
if command -v swiftc >/dev/null; then
  swiftc -O "$HERE/vlog-editor-skill/scripts/cutout.swift" -o "$HERE/vlog-editor-skill/scripts/cutout" && echo "built cutout"
else
  echo "swiftc not found (xcode-select --install) -- thumbnails will work without subject cut-outs"
fi
mkdir -p "$HOME/.claude/skills" "$HOME/Movies/Video Editor Cache" "$HERE/assets" "$HERE/music" "$HERE/projects"
ln -sfn "$HERE/vlog-editor-skill" "$HOME/.claude/skills/vlog-editor"
echo "skill linked: ~/.claude/skills/vlog-editor -> $HERE/vlog-editor-skill"
echo "Next: copy vlog-editor-skill/profiles/example.md to profiles/<your-channel>.md and fill it in."
