$ErrorActionPreference = 'Stop'
$settingsPath = Join-Path $PSScriptRoot '.runtime/settings.json'
if (-not (Test-Path -LiteralPath $settingsPath)) {
    throw 'Setup required. Run environment/install.ps1 first.'
}
$settings = Get-Content -LiteralPath $settingsPath -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not (Test-Path -LiteralPath $settings.python -PathType Leaf)) {
    throw 'Configured Python was moved or removed. Run environment/install.ps1 again.'
}

$pythonArgs = $args
if ($pythonArgs.Count -eq 0) {
    $pythonArgs = @('qwen_smoke_test.py', '--device', $settings.device)
}
$envNames = @('PATH', 'PYTHONPATH', 'PYTHONNOUSERSITE', 'PYTHONDONTWRITEBYTECODE', 'HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE')
$previous = @{}
foreach ($name in $envNames) {
    $previous[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}

Push-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
try {
    $pythonDir = Split-Path -Parent $settings.python
    $env:PATH = "$pythonDir;$($settings.base_dir);$($settings.base_dir)/Library/bin;$($previous['PATH'])"
    $env:PYTHONPATH = $settings.deps
    $env:PYTHONNOUSERSITE = '1'
    $env:PYTHONDONTWRITEBYTECODE = '1'
    $env:HF_HUB_OFFLINE = '1'
    $env:TRANSFORMERS_OFFLINE = '1'
    & $settings.python -X utf8 @pythonArgs
    $result = $LASTEXITCODE
} finally {
    Pop-Location
    foreach ($name in $envNames) {
        [Environment]::SetEnvironmentVariable($name, $previous[$name], 'Process')
    }
}
exit $result
