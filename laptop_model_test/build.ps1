$ErrorActionPreference = 'Stop'
$package = Get-ChildItem -LiteralPath "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Directory |
    Where-Object Name -Like 'BrechtSanders.WinLibs.POSIX.UCRT*' | Select-Object -First 1
if (-not $package) { throw 'WinLibs MinGW is not installed' }
$bin = Join-Path $package.FullName 'mingw64\bin'
$env:PATH = "$bin;$env:PATH"
Push-Location (Join-Path $PSScriptRoot 'sdk')
try {
    & (Join-Path $bin 'mingw32-make.exe') -j4 CC=gcc CXX=g++
    if ($LASTEXITCODE -ne 0) { throw "Build failed: $LASTEXITCODE" }
}
finally { Pop-Location }
