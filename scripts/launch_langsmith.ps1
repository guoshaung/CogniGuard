param(
    [ValidateSet("smoke", "demo", "serve")]
    [string]$Mode = "smoke",
    [int]$Port = 8000,
    [string]$Project = "cogniguard-langgraph",
    [switch]$Submit
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $projectRoot ".venv-langgraph\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "Missing .venv-langgraph Python runtime"
}

$injectedKey = $false
$oldEnabled = $env:COGNIGUARD_LANGSMITH_ENABLED
$oldProject = $env:COGNIGUARD_LANGSMITH_PROJECT
$secretPtr = [IntPtr]::Zero
Push-Location -LiteralPath $projectRoot
try {
    if ($Submit -and -not $env:LANGSMITH_API_KEY) {
        $secureKey = Read-Host "LangSmith API key (input hidden)" -AsSecureString
        $secretPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
        $env:LANGSMITH_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($secretPtr)
        $injectedKey = $true
    }
    $env:COGNIGUARD_LANGSMITH_ENABLED = if ($Submit) { "1" } else { "0" }
    $env:COGNIGUARD_LANGSMITH_PROJECT = $Project
    switch ($Mode) {
        "smoke" {
            if ($Submit) {
                & $python -B -m cogniguard.workflows langsmith smoke --submit
            } else {
                & $python -B -m cogniguard.workflows langsmith smoke
            }
        }
        "demo" { & (Join-Path $projectRoot "run.cmd") demo --json }
        "serve" { & (Join-Path $projectRoot "serve.cmd") $Port }
    }
    exit $LASTEXITCODE
}
finally {
    Pop-Location
    if ($secretPtr -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($secretPtr)
    }
    if ($injectedKey) {
        Remove-Item Env:LANGSMITH_API_KEY -ErrorAction SilentlyContinue
    }
    if ($null -eq $oldEnabled) {
        Remove-Item Env:COGNIGUARD_LANGSMITH_ENABLED -ErrorAction SilentlyContinue
    } else {
        $env:COGNIGUARD_LANGSMITH_ENABLED = $oldEnabled
    }
    if ($null -eq $oldProject) {
        Remove-Item Env:COGNIGUARD_LANGSMITH_PROJECT -ErrorAction SilentlyContinue
    } else {
        $env:COGNIGUARD_LANGSMITH_PROJECT = $oldProject
    }
}
