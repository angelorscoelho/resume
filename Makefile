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
		if command -v gs >/dev/null 2>&1; then \
			gs -sDEVICE=pdfwrite -dCompatibilityLevel=1.4 -dPDFSETTINGS=/printer \
				-dNOPAUSE -dQUIET -dBATCH \
				-sOutputFile=resume_compressed.pdf resume.pdf; \
			if [ -s resume_compressed.pdf ]; then \
				mv resume_compressed.pdf resume.pdf; \
				echo "Compressed resume.pdf: $$(du -sh resume.pdf | cut -f1)"; \
			else \
				echo "Ghostscript compression failed; keeping original resume.pdf" >&2; \
				rm -f resume_compressed.pdf; \
			fi; \
		fi; \
		exit 0; \
	else \
		echo "Failed to build $$out" >&2; \
		exit 2; \
	fi
