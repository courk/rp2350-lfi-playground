#!/usr/bin/env bash
set -e

export DISPLAY=:0

chromium --kiosk --noerrdialogs --disable-infobars "http://127.0.0.1:8080/"
