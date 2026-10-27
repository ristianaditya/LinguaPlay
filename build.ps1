param(
    [string]$Python = (Join-Path $PSScriptRoot '.venv/Scripts/python.exe'),
    [string]$BuildDirectory = (Join-Path $PSScriptRoot '.build'),
    [switch]$Incremental
)
$ErrorActionPreference = 'Stop'
$pythonPath = (Resolve-Path -LiteralPath $Python).Path
$buildPath = [System.IO.Path]::GetFullPath($BuildDirectory)
$savedPath = $env:PATH
try {
    # Prevent unrelated native tools on PATH from contaminating Qt dependencies.
    $env:PATH = "$(Split-Path -Parent $pythonPath);$env:SystemRoot\System32;$env:SystemRoot"
    $cleanArguments = @('--clean')
    if ($Incremental) { $cleanArguments = @() }
    & $pythonPath -m PyInstaller @cleanArguments --noconfirm --windowed --onedir --name LinguaPlay `
        --icon "$PSScriptRoot/assets/app.ico" `
        --add-data "$PSScriptRoot/examples;examples" `
        --add-data "$PSScriptRoot/assets;assets" `
        --add-data "$PSScriptRoot/models;models" `
        --collect-all ctranslate2 --collect-all sentencepiece `
        --collect-submodules winrt --distpath "$PSScriptRoot/portable" `
        --workpath "$buildPath/build" --specpath "$buildPath" "$PSScriptRoot/main.py"
    if ($LASTEXITCODE -ne 0) { throw 'Build portable gagal.' }
} finally {
    $env:PATH = $savedPath
}
