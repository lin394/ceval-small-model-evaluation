$ErrorActionPreference = 'Stop'
$model = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'model.json') -Raw | ConvertFrom-Json
$root = Split-Path -Parent $PSScriptRoot
$name = $model.repo.Split('/')[-1]
$target = Join-Path $root "models/$name"
New-Item -ItemType Directory -Force -Path $target | Out-Null

foreach ($entry in $model.sha256.PSObject.Properties) {
    $file = Join-Path $target $entry.Name
    if ((Test-Path -LiteralPath $file -PathType Leaf) -and
        (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash -eq $entry.Value) {
        Write-Host "Verified $($entry.Name)"
        continue
    }

    $url = "https://huggingface.co/$($model.repo)/resolve/$($model.revision)/$($entry.Name)"
    $part = "$file.$([guid]::NewGuid().ToString('N')).part"
    try {
        Write-Host "Downloading $($entry.Name)"
        & curl.exe --fail --location --retry 2 --connect-timeout 20 --output $part $url
        if ($LASTEXITCODE -ne 0) {
            throw "Download failed for $($entry.Name). Retry setup or copy a verified model into $target."
        }
        if ((Get-FileHash -LiteralPath $part -Algorithm SHA256).Hash -ne $entry.Value) {
            throw "SHA-256 mismatch for $($entry.Name)."
        }
        Move-Item -LiteralPath $part -Destination $file -Force
    } finally {
        if (Test-Path -LiteralPath $part) {
            Remove-Item -LiteralPath $part -Force
        }
    }
}
Set-Content -LiteralPath (Join-Path $target 'revision.txt') -Value $model.revision -Encoding Ascii
