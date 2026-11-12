$ErrorActionPreference='Stop'
$envPath=Join-Path $PSScriptRoot 'backend\.env'
if (!(Test-Path $envPath)) { Write-Host 'FAIL: backend/.env missing. Run .\Configure-KRIYA360-Twilio.ps1.' -ForegroundColor Red; exit 2 }
$lines=Get-Content -LiteralPath $envPath
foreach($key in @('TWILIO_ACCOUNT_SID','TWILIO_AUTH_TOKEN','TWILIO_FROM_NUMBER')) {
 $matches=@($lines|Where-Object {$_ -match ('^\s*'+[regex]::Escape($key)+'\s*=\s*\S+')})
 if($matches.Count -eq 1) {Write-Host "$key : present" -ForegroundColor Green}
 else {Write-Host "$key : missing / empty / duplicated" -ForegroundColor Red}
}
Write-Host 'This checks the configuration file only, NOT running backend credentials or SMS delivery.' -ForegroundColor Yellow
Write-Host 'Restart the backend with .\scripts_start_backend.ps1 and verify API health.'
