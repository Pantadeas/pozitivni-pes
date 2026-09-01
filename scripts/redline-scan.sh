#!/usr/bin/env bash
# Deterministický scan na zakázaný obsah v git diff
# Výstup: exit 0 = PASS, exit 1 = FAIL (s výpisem matchů)
#
# Použití:
#   scripts/redline-scan.sh                    # diff HEAD vs main
#   scripts/redline-scan.sh HEAD~1             # diff HEAD vs HEAD~1
#   scripts/redline-scan.sh --staged           # jen staged changes

set -euo pipefail

REDLINES="knowledge/red-lines.md"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [[ ! -f "$REDLINES" ]]; then
  echo "ERROR: $REDLINES nenalezen" >&2
  exit 2
fi

# --- Sestavení diff ---
if [[ "${1:-}" == "--staged" ]]; then
  DIFF=$(git diff --cached -- '*.dc.html' '*.js' ':!knowledge/' ':!scripts/' ':!docs/')
elif [[ -n "${1:-}" ]]; then
  DIFF=$(git diff "$1" -- '*.dc.html' '*.js' ':!knowledge/' ':!scripts/' ':!docs/')
else
  # Porovnej aktuální branch s main
  BASE=$(git merge-base HEAD main 2>/dev/null || echo "HEAD~1")
  DIFF=$(git diff "$BASE"..HEAD -- '*.dc.html' '*.js' ':!knowledge/' ':!scripts/' ':!docs/')
fi

if [[ -z "$DIFF" ]]; then
  echo "SCAN: žádné změněné soubory k prohledání."
  exit 0
fi

# Jen přidané řádky (začínají +, ale ne +++)
ADDED=$(echo "$DIFF" | grep '^+' | grep -v '^+++' || true)

if [[ -z "$ADDED" ]]; then
  echo "SCAN PASS: žádné přidané řádky."
  exit 0
fi

# --- Klíčová slova z red-lines.md ---
# Extrahujeme řádky ze sekcí ``` bloků
KEYWORDS=$(awk '/^```/{in_block=!in_block; next} in_block{print}' "$REDLINES" | grep -v '^$' || true)

FOUND=0
MATCHES=""

while IFS= read -r keyword; do
  [[ -z "$keyword" ]] && continue
  # Case-insensitive grep s word boundaries kde možné
  if echo "$ADDED" | grep -iE "(^|[[:space:]])${keyword}([[:space:]]|$|[,.!?])" > /dev/null 2>&1; then
    match=$(echo "$ADDED" | grep -inE "(^|[[:space:]])${keyword}([[:space:]]|$|[,.!?])" | head -3)
    MATCHES="${MATCHES}\n  KEYWORD: ${keyword}\n  MATCH:   ${match}\n"
    FOUND=1
  fi
done <<< "$KEYWORDS"

if [[ $FOUND -eq 1 ]]; then
  echo "SCAN FAIL — nalezeny zakázané výrazy:"
  echo -e "$MATCHES"
  echo "Viz knowledge/red-lines.md pro kontext."
  exit 1
else
  echo "SCAN PASS — žádné zakázané výrazy nenalezeny."
  exit 0
fi
