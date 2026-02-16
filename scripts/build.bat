@echo off
setlocal enabledelayedexpansion
set "MAIN="
for %%f in (resume.tex main.tex cv.tex) do if exist "%%f" set "MAIN=%%f"
if "%MAIN%"=="" (
  for %%f in (*.tex) do if not defined MAIN set "MAIN=%%f"
)
if "%MAIN%"=="" (
  echo No .tex files found
  exit /b 1
)
echo Main tex: %MAIN%
where latexmk >nul 2>&1
if %errorlevel%==0 (
  latexmk -pdf -interaction=nonstopmode "%MAIN%" || exit /b %errorlevel%
) else (
  pdflatex -interaction=nonstopmode "%MAIN%" || exit /b %errorlevel%
  pdflatex -interaction=nonstopmode "%MAIN%" || exit /b %errorlevel%
)
for %%A in ("%MAIN%") do set "OUT=%%~nA.pdf"
if exist "%OUT%" (
  copy /Y "%OUT%" "%~dp0resume.pdf" >nul
  echo Built resume.pdf
  exit /b 0
) else (
  echo Failed to build %OUT%
  exit /b 2
)
