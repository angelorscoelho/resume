# Resume Source — Ângelo Coelho

## Project Brief

This repository contains the automated LaTeX source code for the Senior Software Engineer resume of Ângelo Coelho. Local builds write `resume.pdf`, while CI publishes a single-page PDF named `angelorscoelho_resume_XXXXXXXX.pdf`, where `XXXXXXXX` is the last 8 characters of the source commit SHA.

---

## Architecture & Workflow

The resume is authored in LaTeX using a custom document class (`styling.cls`) that defines all typography, colors, spacing, and layout primitives. The main entry point is `main.tex`, which composes the two-column layout using `minipage` blocks and references the custom class for all formatting commands.

```
resume/
├── main.tex          # Resume content and layout composition
├── styling.cls       # Custom LaTeX document class (fonts, colors, commands)
├── fonts/            # Embedded font files (Inter, Source Sans Pro, etc.)
├── icons/            # Contact icon assets (PNG)
├── profile_photo.png # Profile photograph
├── resume.pdf        # Local build output
├── resume-meta.json  # CI metadata for the published PDF
├── Makefile          # Local build shortcut
└── scripts/
    ├── build.sh      # POSIX build script
    └── build.bat     # Windows build script
```

The document requires compilation with **XeLaTeX** (not pdfLaTeX) due to its use of `fontspec` for custom font loading.

---

## Local Build Instructions

Ensure XeLaTeX is installed on your system (`texlive-xetex` on Debian/Ubuntu, MacTeX on macOS).

**Using Make:**

```bash
make pdf
```

**Using the shell script (POSIX):**

```bash
bash scripts/build.sh
```

**Using the shell script (Windows):**

```bat
scripts\build.bat
```

**Manually:**

```bash
xelatex -interaction=nonstopmode main.tex
xelatex -interaction=nonstopmode main.tex
cp main.pdf resume.pdf
```

The double compilation pass is required for LaTeX to resolve all internal references correctly. The final output is written to `resume.pdf` at the repository root.

---

## CI/CD & Portfolio Integration

The repository includes a GitHub Actions workflow defined at `.github/workflows/build-and-publish-resume.yml`.

**Trigger:** Every push to the `main` branch (or manual `workflow_dispatch`).

**Pipeline steps:**

1. Check out the repository with full history.
2. Install `texlive-xetex`, `texlive-latex-extra`, and required font packages on the runner.
3. Compile `main.tex` twice with XeLaTeX to produce `main.pdf`, then rename it to `angelorscoelho_resume_XXXXXXXX.pdf` using the triggering source commit SHA.
4. Write `resume-meta.json` with the full SHA, 8-character suffix, published filename, and build timestamp.
5. Commit and push the updated CI artifact back to `main` using the built-in `GITHUB_TOKEN` (only when the file has changed).
6. Dispatch a `workflow_dispatch` event to the `angelorscoelho/angelorscoelho.dev` repository via the GitHub API, triggering a downstream pipeline that fetches the updated PDF and deploys it to the live portfolio website.
7. Upload the generated PDF as a versioned GitHub Actions artifact for direct download from the Actions run.

The `DEV_REPO_PAT` secret must be configured in the repository settings with sufficient permissions to dispatch workflows on the portfolio repository.
