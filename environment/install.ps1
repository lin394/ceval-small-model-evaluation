param(
    [string]$Python = 'python',
    [ValidateSet('cuda', 'cpu')]
    [string]$Device = 'cuda',
    [switch]$ReuseTorch
)

$ErrorActionPreference = 'Stop'
$Device = $Device.ToLowerInvariant()
$runtime = Join-Path $PSScriptRoot '.runtime'
New-Item -ItemType Directory -Force -Path $runtime | Out-Null
$settingsPath = Join-Path $runtime 'settings.json'
$requirements = Join-Path $PSScriptRoot 'requirements.txt'
$uv = Get-Command uv -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
$uvCache = Join-Path (Split-Path -Parent $PSScriptRoot) '.uv-cache'

function Invoke-Python {
    param([string]$Exe, [string[]]$Arguments)
    & $Exe -X utf8 @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed (exit $LASTEXITCODE): $($Arguments -join ' ')"
    }
}

function Install-Packages {
    param([string]$Exe, [string[]]$Arguments)
    if ($uv) {
        & $uv.Source pip install --cache-dir $uvCache --python $Exe --only-binary ':all:' @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw "uv installation failed (exit $LASTEXITCODE)."
        }
    } else {
        Invoke-Python $Exe (@('-m', 'pip', 'install', '--only-binary=:all:') + $Arguments)
    }
}

$envNames = @('PATH', 'PYTHONPATH', 'PYTHONNOUSERSITE', 'PYTHONDONTWRITEBYTECODE', 'PYTHONUTF8', 'PIP_CACHE_DIR')
$previous = @{}
foreach ($name in $envNames) {
    $previous[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}
try {
    $env:PYTHONPATH = $null
    $env:PYTHONNOUSERSITE = '1'
    $env:PYTHONDONTWRITEBYTECODE = '1'
    $env:PYTHONUTF8 = '1'
    $env:PIP_CACHE_DIR = Join-Path $runtime 'pip-cache'
    $checkPython = "import sys, struct; assert sys.version_info[:2] == (3, 11) and struct.calcsize('P') == 8, 'Use 64-bit Python 3.11'; print(sys.executable)"
    $basePython = Invoke-Python $Python @('-c', $checkPython)
    $baseDir = Split-Path -Parent $basePython
    $env:PATH = "$baseDir;$baseDir/Library/bin;$($previous['PATH'])"
    $checkTorch = "import sys, torch; print('PyTorch:', torch.__version__); print('CUDA:', torch.version.cuda); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'none'); assert sys.argv[1] != 'cuda' or torch.cuda.is_available(), 'CUDA unavailable. Check the NVIDIA driver and PyTorch build.'"

    $deps = $null
    if ($ReuseTorch) {
        $exe = $basePython
        Invoke-Python $exe @('-c', $checkTorch, $Device)
        $deps = Join-Path $runtime '.qwen-deps'
        Install-Packages $exe @('--upgrade', '--target', $deps, '-r', $requirements)
        $env:PYTHONPATH = $deps
    } else {
        $venv = Join-Path $runtime "$Device/.venv"
        $exe = Join-Path $venv 'Scripts/python.exe'
        Invoke-Python $basePython @('-m', 'venv', $venv)
        $index = if ($Device -eq 'cuda') { 'cu128' } else { 'cpu' }
        Install-Packages $exe @("torch==2.11.0+$index", '--index-url', "https://download.pytorch.org/whl/$index")
        Invoke-Python $exe @('-c', $checkTorch, $Device)
        Install-Packages $exe @('-r', $requirements)
    }
    $checkImports = "import pyarrow, transformers; from transformers import AutoModelForCausalLM, AutoTokenizer; print('Transformers:', transformers.__version__, 'PyArrow:', pyarrow.__version__)"
    Invoke-Python $exe @('-c', $checkImports)
    & (Join-Path $PSScriptRoot 'fetch_model.ps1')

    @{ python = $exe; base_dir = $baseDir; deps = $deps; device = $Device } |
        ConvertTo-Json | Set-Content -LiteralPath $settingsPath -Encoding UTF8
    Write-Host 'Setup complete. Run .\environment\run.ps1 from the project root.'
} finally {
    foreach ($name in $envNames) {
        [Environment]::SetEnvironmentVariable($name, $previous[$name], 'Process')
    }
}
