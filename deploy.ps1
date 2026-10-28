# ASCII source keeps this entry point compatible with Windows PowerShell 5.1.
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding
$env:PYTHONUTF8 = '1'
$ProjectRoot = $PSScriptRoot
Set-Location -LiteralPath $ProjectRoot

try {
    $LocalUv = Join-Path $ProjectRoot '.tools\uv\uv.exe'
    if (Test-Path -LiteralPath $LocalUv) {
        $UvPath = $LocalUv
    } elseif (Get-Command uv -CommandType Application -ErrorAction SilentlyContinue) {
        $UvPath = (Get-Command uv -CommandType Application).Source
    } else {
        Write-Host 'Installing uv into .tools/uv (first run only)...'
        Import-Module Microsoft.PowerShell.Security -ErrorAction Stop
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        $env:UV_INSTALL_DIR = Join-Path $ProjectRoot '.tools\uv'
        $env:UV_NO_MODIFY_PATH = '1'
        $Installer = Join-Path ([IO.Path]::GetTempPath()) ([IO.Path]::GetRandomFileName() + '.ps1')
        try {
            Invoke-WebRequest -UseBasicParsing -Uri 'https://astral.sh/uv/install.ps1' -OutFile $Installer
            & $Installer
            if (!$?) { throw 'uv installation failed. Check network access to astral.sh and github.com.' }
        } finally {
            if (Test-Path -LiteralPath $Installer) { Remove-Item -LiteralPath $Installer }
        }
        if (!(Test-Path -LiteralPath $LocalUv)) { throw 'uv.exe was not installed.' }
        $UvPath = $LocalUv
    }

    & $UvPath run --no-project --no-config --no-env-file --python '>=3.11' "$ProjectRoot\scripts\deploy.py" --uv $UvPath @args
    exit $LASTEXITCODE
} catch {
    Write-Host "Deployment failed: $_" -ForegroundColor Red
    exit 1
}
