$ErrorActionPreference='Stop'
Set-Location (Join-Path $PSScriptRoot 'dashboard')
if (!(Test-Path 'node_modules')) { npm install }
npm run dev
