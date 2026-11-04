#!/usr/bin/env bash
# Fails (exit 1) if any sensitive file is publicly readable.
# Usage: scripts/check_exposure.sh [BASE_URL ...]
# A 200 that returns an HTML page is fine (SPA fallback); a 200 with anything else is a leak.
set -u
BASES=("$@")
[ ${#BASES[@]} -eq 0 ] && BASES=(https://kudiarc.xyz https://admin.kudiarc.xyz)

PATHS=(
  /.env /.env.example /.env.local /.env.bak /kudi.db /admin_state.json
  /app.py /db.py /kudisend.py /payouts.py /adminauth.py /deploy.py /requirements.txt
  /.git/HEAD /.git/config /.git/index
  //.env /%2eenv /.env%20 /./.env /static/..%2f.env /.well-known/../.env
)

fail=0
for base in "${BASES[@]}"; do
  for p in "${PATHS[@]}"; do
    out=$(curl -s --path-as-is -m 15 -o /tmp/expo.$$ -w "%{http_code}" "$base$p")
    head=$(head -c 200 /tmp/expo.$$ 2>/dev/null | tr -d '\r\0')
    case "$out" in
      200)
        if printf '%s' "$head" | grep -qiE '^\s*(<!doctype html|<html)'; then
          printf 'ok    %s%s (html fallback)\n' "$base" "$p"
        else
          printf 'LEAK  %s%s -> 200 non-HTML content\n' "$base" "$p"; fail=1
        fi ;;
      000) printf 'WARN  %s%s unreachable\n' "$base" "$p"; fail=1 ;;
      *)   printf 'ok    %s%s -> %s\n' "$base" "$p" "$out" ;;
    esac
  done
done
rm -f /tmp/expo.$$
[ $fail -eq 0 ] && echo "PASS: nothing sensitive is served" || echo "FAIL: fix before going live"
exit $fail
