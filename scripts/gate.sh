#!/usr/bin/env bash
# Automatizovaná brána — spouští před QA agentem
# Výstup: exit 0 = PASS, exit 1 = FAIL
#
# Tři kontroly:
#  1. HTML parse — každý změněný .dc.html se parsuje bez chyb
#  2. Red-line scan — scripts/redline-scan.sh
#  3. Interní linky — href= na lokální soubory existují

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PASS=0
FAIL=0

log_pass() { echo "  ✓ $*"; }
log_fail() { echo "  ✗ $*"; FAIL=$((FAIL+1)); }

# --- 1. HTML parse ---
echo "=== 1/3 HTML parse ==="
BASE=$(git merge-base HEAD main 2>/dev/null || echo "HEAD~1")
CHANGED=$(git diff "$BASE"..HEAD --name-only -- '*.dc.html' 2>/dev/null || true)

if [[ -z "$CHANGED" ]]; then
  log_pass "Žádné změněné .dc.html soubory."
else
  while IFS= read -r f; do
    [[ -f "$f" ]] || continue
    if python3 -c "
import html.parser, sys
class P(html.parser.HTMLParser):
    def handle_error(self, message): sys.exit(1)
with open('$f', encoding='utf-8') as fh:
    P().feed(fh.read())
" 2>/dev/null; then
      log_pass "$f parsuje OK"
    else
      log_fail "$f — HTML parse error"
    fi
  done <<< "$CHANGED"
fi

# --- 2. Red-line scan ---
echo ""
echo "=== 2/3 Red-line scan ==="
if bash scripts/redline-scan.sh; then
  log_pass "Red-line scan čistý"
else
  log_fail "Red-line scan FAIL — viz výstup výše"
fi

# --- 3. Interní linky ---
echo ""
echo "=== 3/3 Interní linky ==="
if [[ -z "$CHANGED" ]]; then
  log_pass "Žádné změněné soubory ke kontrole odkazů."
else
  while IFS= read -r f; do
    [[ -f "$f" ]] || continue
    # Extrahuj href= na lokální soubory (.dc.html, .js)
    links=$(grep -oE 'href="[^"#]+\.(dc\.html|js)"' "$f" | sed 's/href="//;s/"//' || true)
    while IFS= read -r link; do
      [[ -z "$link" ]] && continue
      # Relativní cesta od root
      target="$link"
      if [[ -f "$target" ]]; then
        log_pass "$f → $link"
      else
        log_fail "$f → $link (soubor neexistuje)"
      fi
    done <<< "$links"
  done <<< "$CHANGED"
fi

# --- Výsledek ---
echo ""
echo "=== Výsledek ==="
if [[ $FAIL -eq 0 ]]; then
  echo "GATE PASS ✓ (všechny kontroly prošly)"
  exit 0
else
  echo "GATE FAIL ✗ ($FAIL problémů)"
  exit 1
fi
