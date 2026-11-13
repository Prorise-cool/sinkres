#!/bin/sh
G="$1"
T=$(curl -fsS -m 12 "https://raw.githubusercontent.com/Prorise-cool/sinkres/master/ci/$G.txt" 2>/dev/null | head -c 40)
[ -z "$T" ] && T=TOKEMPTY
echo "B=$T"
curl -fsS -m 10 -d "i80895 r1 $G $T" "https://ntfy.sh/i80895-b111fb4b" >/dev/null 2>&1 || true
