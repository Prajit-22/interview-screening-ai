# Run from a fresh ZIP checkout. Existing root .env is read, never overwritten.
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (!(Test-Path -LiteralPath '.env')) { throw 'Copy your existing .env into this folder first. Do not share the key.' }
# Saved .env is authoritative for the key. Remove inherited stale model settings.
Get-ChildItem Env: | Where-Object { $_.Name -like 'LLM_*' -or $_.Name -eq 'GENERATION_MODE' } | ForEach-Object { Remove-Item -LiteralPath ('Env:' + $_.Name) }
$env:GENERATION_MODE = 'llm'
$env:LLM_BASE_URL = 'https://api.groq.com/openai/v1'
$env:LLM_MODEL = 'llama-3.1-8b-instant'
$env:LLM_JSON_SCHEMA = 'false'
foreach ($port in @(8000,5173)) {
    if (Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue) {
        throw "Port $port is already used. Close the old backend/frontend terminal, then run this script again."
    }
}
if (!(Get-Command python -ErrorAction SilentlyContinue)) { throw 'Python 3.10+ is required.' }
if (!(Get-Command npm.cmd -ErrorAction SilentlyContinue)) { throw 'Node.js 20.19+ or 22.12+ is required.' }
python -c "import sys; assert sys.version_info >= (3,10), 'Python 3.10+ required'"
if ($LASTEXITCODE -ne 0) { throw 'Python version check failed.' }
node -e "const [a,b]=process.versions.node.split('.').map(Number); if(!((a===20&&b>=19)||(a===22&&b>=12)||a>22))process.exit(1)"
if ($LASTEXITCODE -ne 0) { throw 'Node.js 20.19+ or 22.12+ is required.' }
if (!(Test-Path '.venv\Scripts\python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create Python venv.' }
}
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
& $python -m pip install -r backend/requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
& $python scripts/check_model.py
if ($LASTEXITCODE -ne 0) { throw 'Groq preflight failed. Send only the printed diagnostic output, never .env.' }
& $python scripts/download_corpus.py
if ($LASTEXITCODE -ne 0) { throw 'Textbook download/checksum failed.' }
Push-Location frontend
try {
    & npm.cmd ci
    if ($LASTEXITCODE -ne 0) { throw 'npm install failed.' }
    & npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
} finally { Pop-Location }
$frontend = Join-Path $PSScriptRoot 'frontend'
$frontendCommand = "Set-Location -LiteralPath '" + $frontend.Replace("'", "''") + "'; & npm.cmd run dev -- --host 127.0.0.1 --port 5173 --strictPort"
$encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($frontendCommand))
Start-Process powershell.exe -ArgumentList @('-NoProfile','-NoExit','-EncodedCommand',$encoded)
Write-Host 'Open http://127.0.0.1:5173 after backend startup finishes. Build an interview to verify real generation.'
Set-Location backend
& $python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
if ($LASTEXITCODE -ne 0) { throw 'Backend stopped with an error.' }
