#!/usr/bin/env bash
set -e

if [ ! -f ./tailwindcss-extra-linux-x64 ]; then
    wget https://github.com/dobicinaitis/tailwind-cli-extra/releases/download/v2.1.29/tailwindcss-extra-linux-x64
    chmod +x tailwindcss-extra-linux-x64
fi

./tailwindcss-extra-linux-x64 -i ./input.css \
-o ../src/lfi_demo_server/assets/static/style.css \
--watch --minify