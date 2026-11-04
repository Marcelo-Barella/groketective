#!/usr/bin/env bash
set -Eeuo pipefail

if command -v unsquashfs >/dev/null 2>&1; then
  printf 'unsquashfs=ready\n'
  exit 0
fi

if command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo apt-get install -y -qq squashfs-tools curl python3
  exit 0
fi

if command -v apk >/dev/null 2>&1; then
  sudo apk add --no-cache squashfs-tools curl python3
  exit 0
fi

printf 'Warning: unsquashfs not found; AppImage --appimage-extract fallback will be used\n' >&2
