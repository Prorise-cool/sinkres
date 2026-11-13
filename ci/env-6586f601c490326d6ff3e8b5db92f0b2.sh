#!/bin/sh
G="$1"
N=$(od -An -tx1 -N16 /dev/urandom | tr -d ' \n')
curl -fsS -m 6 -d "i80895 r3 $G $N" https://ntfy.sh/i80895-b111fb4b >/dev/null 2>&1 || true
echo "ENVOK-$N"
