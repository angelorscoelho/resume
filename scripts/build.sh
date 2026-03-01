#!/usr/bin/env bash
set -euo pipefail
# Build resume PDF using XeLaTeX (required for fontspec/custom fonts)
main="main.tex"
for f in resume.tex main.tex cv.tex; do
  [ -f "$f" ] && { main="$f"; break; }
done

echo "Building: $main"
xelatex -interaction=nonstopmode "$main"
xelatex -interaction=nonstopmode "$main"

out="${main%.tex}.pdf"
if [ -f "$out" ]; then
  cp -f "$out" resume.pdf
  echo "Built resume.pdf"
else
  echo "Failed to build $out" >&2
  exit 2
fi
