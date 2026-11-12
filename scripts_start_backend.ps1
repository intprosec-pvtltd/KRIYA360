$ErrorActionPreference='Stop'
Set-Location (Join-Path $PSScriptRoot 'backend')
if (!(Test-Path '.venv\Scripts\python.exe')) { py -3.11 -m venv .venv }
& '.\.venv\Scripts\python.exe' -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {throw 'Backend dependency installation failed'}
if (!$env:JWT_SECRET) {$env:JWT_SECRET='KRIYA360-LOCAL-DEMO-ONLY-REPLACE-BEFORE-DEPLOY'}
# --env-file loads private SMS credentials inside the Uvicorn reloader and worker.
$arguments = @('-m','uvicorn','app.main:app','--host','0.0.0.0','--port','8000','--reload')
if (Test-Path '.env') { $arguments += @('--env-file',(Resolve-Path '.env').Path) }
# Diagnostics only: never print credential values or OTPs.
if (Test-Path '.env') { Write-Host 'KRIYA360 backend .env detected and passed to Uvicorn.' -ForegroundColor Green }
else { Write-Warning 'No backend/.env found. Customer SMS will fail until Configure-KRIYA360-Twilio.ps1 is run.' }
& '.\.venv\Scripts\python.exe' @arguments
