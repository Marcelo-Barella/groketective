#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  printf 'Usage: %s --appimage PATH --output-dir DIR\n' "$0"
}

die() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

appimage=""
output_dir=""

while (($#)); do
  case "$1" in
    --appimage)
      (($# >= 2)) || die "--appimage requires a value"
      appimage="$2"
      shift 2
      ;;
    --output-dir)
      (($# >= 2)) || die "--output-dir requires a value"
      output_dir="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "Unknown argument: $1"
      ;;
  esac
done

[[ -f "$appimage" ]] || die "AppImage not found: $appimage"
[[ -n "$output_dir" ]] || die "--output-dir is required"

mkdir -p "$output_dir"

if command -v unsquashfs >/dev/null 2>&1; then
  if unsquashfs -force -dest "$output_dir" "$appimage" >/dev/null 2>&1; then
    printf 'extracted_via=unsquashfs\n'
    printf 'output_dir=%s\n' "$output_dir"
    exit 0
  fi
  rm -rf "${output_dir:?}"/*
fi

work_dir=$(mktemp -d)
trap 'rm -rf "$work_dir"' EXIT
cp "$appimage" "$work_dir/grok-bot.AppImage"
chmod +x "$work_dir/grok-bot.AppImage"
(
  cd "$work_dir"
  ./grok-bot.AppImage --appimage-extract >/dev/null 2>&1
)
[[ -d "$work_dir/squashfs-root" ]] || die "AppImage extraction failed"
shopt -s dotglob
mv "$work_dir/squashfs-root"/* "$output_dir/"
shopt -u dotglob
printf 'extracted_via=appimage-extract\n'
printf 'output_dir=%s\n' "$output_dir"
