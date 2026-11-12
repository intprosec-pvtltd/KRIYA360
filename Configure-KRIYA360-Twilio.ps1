$ErrorActionPreference = 'Stop'
$backend = Join-Path $PSScriptRoot 'backend'
$target = Join-Path $backend '.env'
Write-Host 'Configure your Twilio SMS credentials for local KRIYA360 testing.' -ForegroundColor Cyan
Write-Host 'The new Auth Token should be rotated because the earlier token was exposed.' -ForegroundColor Yellow
$sid = (Read-Host 'Twilio Account SID').Trim()
$sender = (Read-Host 'Twilio sender number, for example +1...').Trim()
$secure = Read-Host 'Twilio Auth Token (hidden)' -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try { $token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
if ($sid -notmatch '^AC[a-fA-F0-9]{32}$' -or $sender -notmatch '^\+[1-9][0-9]{7,14}$' -or [string]::IsNullOrWhiteSpace($token)) { Remove-Variable token -ErrorAction SilentlyContinue; throw 'Invalid SID, sender format, or missing token.' }
if (Test-Path $target) { Copy-Item $target ($target+'.backup-'+(Get-Date -Format yyyyMMddHHmmss)) }
# Keep any existing non-Twilio variables, but replace previous Twilio entries.
$rest = @()
if (Test-Path $target) { $rest = @(Get-Content $target | Where-Object {$_ -notmatch '^\s*TWILIO_(ACCOUNT_SID|AUTH_TOKEN|FROM_NUMBER)\s*='}) }
# Reject control characters/newlines to protect .env structure.
foreach ($v in @($sid,$sender,$token)) { if ($v -match '[\r\n\x00]') { throw 'A value contains invalid control characters.' } }
$contents = @($rest)+@('TWILIO_ACCOUNT_SID='+$sid,'TWILIO_AUTH_TOKEN='+$token,'TWILIO_FROM_NUMBER='+$sender)
[System.IO.File]::WriteAllLines($target, [string[]]$contents, [System.Text.UTF8Encoding]::new($false))
Remove-Variable token, secure -ErrorAction SilentlyContinue
Write-Host 'Saved local backend/.env. This file contains secrets: do not share, upload, or commit it.' -ForegroundColor Green
Write-Host 'Restart backend using scripts_start_backend.ps1. The launcher will load .env automatically.'
