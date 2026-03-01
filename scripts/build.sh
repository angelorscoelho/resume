#!/usr/bin/env bash
set -euo pipefail
# Run the Makefile pdf target; useful for CI and local builds
if command -v make >/dev/null 2>&1; then
  make pdf
else
  echo "make not found; trying to run Makefile target manually" >&2
  # Fallback: try to find main .tex and run latexmk/pdflatex directly
  main=""
  for f in resume.tex main.tex cv.tex; do
    [ -f "$f" ] && { main="$f"; break; }
  done
  if [ -z "$main" ]; then
    main=$(ls *.tex 2>/dev/null | head -n1 || true)
  fi
  if [ -z "$main" ]; then
    echo "No .tex files found" >&2
    exit 1
  fi
  if command -v latexmk >/dev/null 2>&1; then
    latexmk -xelatex -interaction=nonstopmode "$main"
  else
    xelatex -interaction=nonstopmode "$main" || true
    xelatex -interaction=nonstopmode "$main"
  fi
  out="${main%.tex}.pdf"
  if [ -f "$out" ]; then
    cp -f "$out" resume.pdf
    echo "Built resume.pdf"
    if command -v gs >/dev/null 2>&1; then
      gs -sDEVICE=pdfwrite -dCompatibilityLevel=1.4 -dPDFSETTINGS=/printer \
        -dNOPAUSE -dQUIET -dBATCH \
        -sOutputFile=resume_compressed.pdf resume.pdf
      if [ -s resume_compressed.pdf ]; then
        mv resume_compressed.pdf resume.pdf
        echo "Compressed resume.pdf: $(du -sh resume.pdf | cut -f1)"
      else
        echo "Ghostscript compression failed; keeping original resume.pdf" >&2
        rm -f resume_compressed.pdf
      fi
    fi
  else
    echo "Failed to build $out" >&2
    exit 2
  fi
fi
