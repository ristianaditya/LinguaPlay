$ErrorActionPreference = 'Stop'
$dataDirectory = Join-Path $env:LOCALAPPDATA 'LinguaPlay'
$runtimeFile = Join-Path $dataDirectory 'local-runtime.json'
$settingsFile = Join-Path $dataDirectory 'settings.json'
if (!(Test-Path -LiteralPath $runtimeFile) -or !(Test-Path -LiteralPath $settingsFile)) { exit 0 }

function Test-LocalServer {
    try {
        $request = [System.Net.WebRequest]::Create('http://127.0.0.1:11434/api/version')
        $request.Proxy = $null
        $request.Timeout = 1000
        $response = $request.GetResponse()
        $response.Close()
        return $true
    } catch { return $false }
}

try {
    $settings = Get-Content -LiteralPath $settingsFile -Raw | ConvertFrom-Json
    $endpoint = [Uri]$settings.endpoint
    if ($settings.kind -ne 'OpenAI compatible' -or $endpoint.Host -notin @('localhost','127.0.0.1') -or $endpoint.Port -ne 11434) { exit 0 }
    if (Test-LocalServer) { exit 0 }
    $runtime = Get-Content -LiteralPath $runtimeFile -Raw | ConvertFrom-Json
    if (!(Test-Path -LiteralPath $runtime.executable -PathType Leaf)) { throw 'Runtime Ollama lokal tidak ditemukan.' }
    # Environment changes apply only to this launcher and its child process.
    $env:OLLAMA_HOST = '127.0.0.1:11434'
    $env:OLLAMA_MODELS = $runtime.models
    $env:OLLAMA_NO_CLOUD = '1'
    $env:OLLAMA_NUM_PARALLEL = '1'
    $env:OLLAMA_MAX_LOADED_MODELS = '1'
    $env:OLLAMA_CONTEXT_LENGTH = '2048'
    $env:OLLAMA_KEEP_ALIVE = '5m'
    $runtimeDirectory = Split-Path -Parent $runtime.executable
    $env:PATH = "$runtimeDirectory;$env:SystemRoot\System32;$env:SystemRoot"
    $server = Start-Process -FilePath $runtime.executable -ArgumentList 'serve' -WorkingDirectory $runtimeDirectory -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $dataDirectory 'ollama-stdout.log') -RedirectStandardError (Join-Path $dataDirectory 'ollama-stderr.log')
    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        if (Test-LocalServer) { exit 0 }
        if ($server.HasExited) { throw 'Ollama berhenti sebelum siap.' }
        Start-Sleep -Milliseconds 250
    }
    throw 'Ollama belum siap setelah menunggu. Periksa ollama-stderr.log di folder data LinguaPlay.'
} catch {
    Write-Host "Model lokal belum siap: $($_.Exception.Message)"
    exit 1
}
