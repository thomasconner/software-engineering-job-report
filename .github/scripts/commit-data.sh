#!/usr/bin/env bash
# Commit and push changes under the given paths as "data: refresh <YYYY-MM>".
# Prints changed=true|false and site_changed=true|false to $GITHUB_OUTPUT.
set -euo pipefail

paths=()
for p in "$@"; do
  [ -e "$p" ] && paths+=("$p")
done
[ ${#paths[@]} -gt 0 ] && git add -A -- "${paths[@]}"

if git diff --cached --quiet; then
  echo "no changes under $*"
  echo "changed=false" >> "$GITHUB_OUTPUT"
  exit 0
fi

# Name the newest month touched: data/raw/<kind>/<YYYY-MM>/... or data/answers/<model>/<YYYY-MM>.parquet.
month=$(git diff --cached --name-only \
  | sed -nE 's#^data/(raw/[^/]+/|answers/[^/]+/)([0-9]{4}-[0-9]{2}).*#\2#p' \
  | sort | tail -n 1)
[ -n "$month" ] || month=$(jq -r '.latest_month // empty' site/data/metrics.json 2>/dev/null || true)
[ -n "$month" ] || month=$(date -u +%Y-%m)

if git diff --cached --quiet -- site; then site=false; else site=true; fi

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git commit -m "data: refresh $month"
git pull --rebase --autostash origin "$GITHUB_REF_NAME"
git push origin "HEAD:$GITHUB_REF_NAME"

echo "changed=true" >> "$GITHUB_OUTPUT"
echo "site_changed=$site" >> "$GITHUB_OUTPUT"
