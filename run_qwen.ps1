param(
    [string]$Python = 'D:/Anaconda3/envs/warehouse-gpu/python.exe',
    [ValidateSet('auto', 'cpu', 'cuda')]
    [string]$Device = 'auto',
    [string]$Prompt,
    [switch]$Trial
)

$ErrorActionPreference = 'Stop'
$pythonDir = Split-Path -Parent (Resolve-Path -LiteralPath $Python).Path
$deps = Join-Path $PSScriptRoot '.qwen-deps'
$previousPath = $env:PATH
$previousPythonPath = $env:PYTHONPATH
$previousBytecode = $env:PYTHONDONTWRITEBYTECODE
$arguments = @('--device', $Device)
if ($Trial) {
    $arguments += '--trial'
}
if ($PSBoundParameters.ContainsKey('Prompt')) {
    $arguments += @('--prompt', $Prompt)
}
try {
    $env:PATH = "$pythonDir;$pythonDir/Library/bin;$previousPath"
    $env:PYTHONPATH = $deps
    $env:PYTHONDONTWRITEBYTECODE = '1'
    & $Python -X utf8 (Join-Path $PSScriptRoot 'qwen_smoke_test.py') @arguments
    $result = $LASTEXITCODE
} finally {
    $env:PATH = $previousPath
    $env:PYTHONPATH = $previousPythonPath
    $env:PYTHONDONTWRITEBYTECODE = $previousBytecode
}
exit $result
