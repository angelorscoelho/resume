#!/usr/bin/env node
/**
 * Resume PDF build script
 * Compiles main.tex using XeLaTeX (required for custom fonts)
 * Outputs: resume.pdf
 *
 * Supported LaTeX distributions:
 *   - MiKTeX (auto-detected at AppData\Local\Programs\MiKTeX)
 *   - TeX Live (if xelatex is on system PATH)
 */

const { spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');

const root = path.resolve(__dirname, '..');
const mainTex = 'main.tex';
const outputPdf = path.join(root, 'main.pdf');
const resumePdf = path.join(root, 'resume.pdf');

// --- Resolve xelatex binary ---
function findXelatex() {
  // 1. Check system PATH
  const check = spawnSync(
    process.platform === 'win32' ? 'where' : 'which',
    ['xelatex'],
    { encoding: 'utf8' }
  );
  if (check.status === 0 && check.stdout.trim()) {
    return 'xelatex';
  }

  if (process.platform !== 'win32') return null;

  // 2. MiKTeX user install (Windows)
  const miktexUserBin = path.join(
    os.homedir(),
    'AppData', 'Local', 'Programs', 'MiKTeX', 'miktex', 'bin', 'x64'
  );
  const xelatexWrapper = path.join(miktexUserBin, 'xelatex.exe');
  if (fs.existsSync(xelatexWrapper)) return xelatexWrapper;

  // 3. miktex-xetex fallback (same bin folder, needs format flag)
  const miktexXetex = path.join(miktexUserBin, 'miktex-xetex.exe');
  if (fs.existsSync(miktexXetex)) return miktexXetex;

  // 4. MiKTeX system install
  const miktexSystemBin = 'C:\\Program Files\\MiKTeX\\miktex\\bin\\x64';
  const sysXelatex = path.join(miktexSystemBin, 'xelatex.exe');
  if (fs.existsSync(sysXelatex)) return sysXelatex;
  const sysMiktexXetex = path.join(miktexSystemBin, 'miktex-xetex.exe');
  if (fs.existsSync(sysMiktexXetex)) return sysMiktexXetex;

  return null;
}

const xelatexBin = findXelatex();

if (!xelatexBin) {
  console.error('\n[ERROR] XeLaTeX not found.');
  console.error('Install MiKTeX: https://miktex.org/download');
  console.error('Or TeX Live: https://tug.org/texlive/\n');
  process.exit(1);
}

console.log(`[BUILD] Using XeLaTeX: ${xelatexBin}`);

// Determine if we're using miktex-xetex directly (needs extra args)
const isMiktexXetex = path.basename(xelatexBin).toLowerCase() === 'miktex-xetex.exe';
const compileArgs = isMiktexXetex
  ? ['--interaction=nonstopmode', '--undump=xelatex', mainTex]
  : ['-interaction=nonstopmode', mainTex];

// Inject MiKTeX bin into PATH so sub-processes can resolve dependencies
const miktexBinDir = path.dirname(xelatexBin);
const env = { ...process.env, PATH: `${miktexBinDir};${process.env.PATH}` };

function compile(pass) {
  console.log(`\n[BUILD] XeLaTeX pass ${pass}/2...`);
  const result = spawnSync(xelatexBin, compileArgs, {
    cwd: root,
    encoding: 'utf8',
    stdio: 'inherit',
    env
  });
  if (result.status !== 0) {
    console.error(`[ERROR] XeLaTeX pass ${pass} failed. Check main.log for details.`);
    process.exit(1);
  }
}

compile(1);
compile(2);

if (!fs.existsSync(outputPdf)) {
  console.error('[ERROR] main.pdf not found after compilation.');
  process.exit(1);
}

fs.copyFileSync(outputPdf, resumePdf);
console.log('\n[SUCCESS] resume.pdf generated successfully.\n');
