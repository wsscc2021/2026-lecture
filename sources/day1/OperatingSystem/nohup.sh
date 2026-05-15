#!/usr/bin/env bash

echo "Started at: $(date)"
echo "PID: $$"

count=1

while true; do
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] running... count=$count"
  count=$((count + 1))
  sleep 5
done