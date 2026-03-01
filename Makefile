PDF:=$(shell for f in resume.tex main.tex cv.tex; do [ -f "$$f" ] && { echo "$$f"; exit; }; done; echo $$(ls *.tex 2>/dev/null | head -n1))

.PHONY: pdf
pdf:
	@set -e; \
	main="$(PDF)"; \
	if [ -z "$$main" ] || [ "$$main" = "" ]; then main=$$(ls *.tex 2>/dev/null | head -n1 || true); fi; \
	if [ -z "$$main" ]; then echo "No .tex files found" >&2; exit 1; fi; \
	echo "Main tex: $$main"; \
	if command -v latexmk >/dev/null 2>&1; then \
		latexmk -xelatex -interaction=nonstopmode "$$main"; \
		status=$$?; \
	else \
		xelatex -interaction=nonstopmode "$$main" || true; \
		xelatex -interaction=nonstopmode "$$main"; \
		status=$$?; \
	fi; \
	out=$$(basename "$$main" .tex).pdf; \
	if [ -f "$$out" ]; then \
		cp -f "$$out" resume.pdf; \
		echo "Built resume.pdf"; \
		exit 0; \
	else \
		echo "Failed to build $$out" >&2; \
		exit 2; \
	fi
