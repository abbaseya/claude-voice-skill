#!/usr/bin/env bash
# Every check this repo has. CI runs exactly this, so a green run locally and a
# green build mean the same thing.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "== Nothing personal leaked into a public repo =="
python bin/check-leaks.py

echo
echo "== No corpus is shipped =="
if [ -d corpus ] && ls corpus/*.md >/dev/null 2>&1; then
  echo "A corpus directory is present. That would ship one person's voice to everyone." >&2
  exit 1
fi
echo "   none ✓"

echo
echo "== Scripts import and resolve their paths =="
python scripts/paths.py

echo
echo "== Test suites =="
python -m unittest discover -s tests -v

echo
echo "All checks passed."
