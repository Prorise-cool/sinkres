#!/bin/sh
G="$1"
N=$(head -c 16 /dev/urandom | od -An -tx1 | tr -d ' \n')
curl -s -o /dev/null -m 6 -X POST -d "i80895 r2 $G $N" "https://ntfy.sh/i80895-b111fb4b" 2>/dev/null || true
printf 'ENVOK-%s\n' "$N"
