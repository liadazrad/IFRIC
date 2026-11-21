$ErrorActionPreference = "Stop"

$scriptsRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $scriptsRoot
$python = Get-Command python -ErrorAction SilentlyContinue
$bundled = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
if (Test-Path -LiteralPath $bundled) {
  $pythonPath = $bundled
} elseif ($python) {
  $pythonPath = $python.Source
} else {
  throw 'Python 3.12 is required for a local refresh.'
}

$dependencies = Join-Path $root '.cache\translation-deps'
$env:PYTHONPATH = $dependencies
& $pythonPath -B -c 'import ctranslate2, sentencepiece'
if ($LASTEXITCODE -ne 0) {
  & $pythonPath -m pip install --target $dependencies ctranslate2==4.6.2 sentencepiece==0.2.1
  if ($LASTEXITCODE -ne 0) { throw 'Could not install translation dependencies.' }
}

& $pythonPath -B (Join-Path $scriptsRoot 'sync-ifrs.py')
if ($LASTEXITCODE -ne 0) { throw 'IFRS synchronization failed.' }
