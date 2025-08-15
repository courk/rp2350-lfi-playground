#!/usr/bin/env bash

TARGET="raspberrypi.local" # Assume mDNS is working
VERSION=$(git describe --tags)

cd ..
rsync -ravc --prune-empty-dirs lfi-demo-server \
--include "*/" \
--include "firmware/build/firmware.uf2" \
--include "firmware/firmware.c" \
--exclude ".git/**" \
--exclude ".gitignore" \
--exclude ".gitmodules" \
--exclude ".pre-commit-config.yaml" \
--exclude "__pycache__/**" \
--exclude ".mypy_cache/**" \
--exclude ".ruff_cache/**" \
--exclude ".pre-commit-config.yaml" \
--exclude "deploy.sh" \
--exclude "firmware/**" \
--exclude "ui_tools/**" \
$TARGET:.

ssh $TARGET "echo '$VERSION' > lfi-demo-server/.version"
