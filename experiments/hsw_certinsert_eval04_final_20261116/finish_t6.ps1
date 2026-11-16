param(
    [Parameter(Mandatory=$true)][int]$QwenRunnerPid
)

$ErrorActionPreference = 'Stop'
$experiment = $PSScriptRoot
$worktree = (Resolve-Path -LiteralPath (Join-Path $experiment '../..')).Path
$relative = 'experiments/hsw_certinsert_eval04_final_20261116'
$output = Join-Path $worktree 'var/results/hsw-st/certinsert_eval04_final_20261116'
$py = Join-Path $worktree 'var/results/hsw-st/certinsert_eval04_20261113/runtime/Scripts/python.exe'
$ocr = Join-Path $worktree 'var/results/hsw-st/certinsert_eval_20261111_01/run01/runtime/ocr/Scripts/python.exe'
$env:PYTHONUTF8 = '1'
$env:HF_MODULES_CACHE = Join-Path $output 'nomic_modules'
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$env:PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK = 'True'
$env:OMP_NUM_THREADS = '2'
$env:MKL_NUM_THREADS = '2'
$env:OPENBLAS_NUM_THREADS = '2'

function Run-Step([string]$Python, [string]$File, [string[]]$Arguments) {
    Write-Output "Running $File $Arguments"
    & $Python -B "$experiment/$File" @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$File exited with $LASTEXITCODE" }
}

function Publish-Step([string]$Message, [string[]]$Files) {
    if ((git -C $worktree branch --show-current) -ne 'codex/hsw-st') { throw 'Wrong worktree branch' }
    if (git -C $worktree diff --cached --name-only) { throw 'Existing staged files' }
    $paths = $Files | ForEach-Object { "$relative/$_" }
    git -C $worktree add --sparse -- $paths
    if ($LASTEXITCODE -ne 0) { throw 'Stage failed' }
    $staged = git -C $worktree diff --cached --name-only
    if (Compare-Object ($paths | Sort-Object) ($staged | Sort-Object)) { throw 'Stage scope mismatch' }
    git -C $worktree diff --cached --check
    if ($LASTEXITCODE -ne 0) { throw 'Diff check failed' }
    git -C $worktree commit -m $Message
    if ($LASTEXITCODE -ne 0) { throw 'Commit failed' }
    git -C $worktree push origin codex/hsw-st
    if ($LASTEXITCODE -ne 0) { throw 'Push failed' }
    $head = git -C $worktree rev-parse HEAD
    $remote = (git -C $worktree ls-remote --exit-code origin refs/heads/codex/hsw-st).Split()[0]
    if ($head -ne $remote) { throw 'Remote branch mismatch' }
    Write-Output "Verified remote $remote"
    return $remote
}

$baseline = "$output/stage_d_model_arms/baseline/RESULT.json"
while (-not (Test-Path -LiteralPath $baseline)) {
    $running = Get-CimInstance Win32_Process -Filter "ProcessId = $QwenRunnerPid"
    if (-not $running -or $running.CommandLine -notmatch 't6_qwen_flow\.py') {
        throw 'Qwen queue exited before writing its final result'
    }
    Start-Sleep -Seconds 30
}

if (-not (Test-Path -LiteralPath "$output/postmark/RESULT.json")) {
    Run-Step $py 't6_postmark.py' @('generate')
}

if (-not (Test-Path -LiteralPath "$output/score_registry.json")) {
    Run-Step $py 't6_registry.py' @()
}
if (-not (Test-Path -LiteralPath "$experiment/T6_VARIANT_FREEZE.json")) {
    Run-Step $py 'prepare_t6_next.py' @('variants')
    Publish-Step 'Freeze the complete T6 variant and compression registry' @('T6_VARIANT_FREEZE.json')
}

if (-not (Test-Path -LiteralPath "$output/ocr/RESULT.json")) {
    Run-Step $ocr 't6_ocr.py' @()
}
if (-not (Test-Path -LiteralPath "$output/stage_d_model_arms/compress/RESULT.json")) {
    Run-Step $py 't6_model_arms.py' @('compress')
}
if (-not (Test-Path -LiteralPath "$output/baseline_public_gate.json")) {
    Run-Step $py 't6_metrics.py' @('public_gate')
}
if (-not (Test-Path -LiteralPath "$output/frequency/all/manifest.json")) {
    Run-Step $py 't6_frequency.py' @()
}
if (-not (Test-Path -LiteralPath "$experiment/T6_P1_FREEZE.json")) {
    Run-Step $py 'prepare_t6_next.py' @('p1')
    Publish-Step 'Freeze all T6 frequency-observation inputs before scoring' @('T6_P1_FREEZE.json')
}
if (-not (Test-Path -LiteralPath "$output/scores/all_frequency.json")) {
    Run-Step $py 't6_metrics.py' @('frequency')
}
if (-not (Test-Path -LiteralPath "$output/scores/all_variants.json")) {
    Run-Step $py 't6_metrics.py' @('variants')
}
if (-not (Test-Path -LiteralPath "$output/scores/baseline_fpr.json")) {
    Run-Step $py 't6_metrics.py' @('baseline_fpr')
}
if (-not (Test-Path -LiteralPath "$output/cpu_controls/fpr.json")) {
    Run-Step $py 't6_controls.py' @('background')
}
if (-not (Test-Path -LiteralPath "$experiment/RESULT.md")) {
    Run-Step $py 'report_t6.py' @()
}
Publish-Step 'Publish the T6 dual-embedder evaluation and controls' @('RESULT.md','per_item.csv','figure_counts.json')

$head = git -C $worktree rev-parse HEAD
foreach ($file in @('RESULT.md','per_item.csv','figure_counts.json')) {
    $blob = git -C $worktree rev-parse "${head}:$relative/$file"
    $remoteBlob = gh api "repos/guoshaung/CogniGuard/git/blobs/$blob" --jq '.sha'
    if ($LASTEXITCODE -ne 0 -or $remoteBlob -ne $blob) { throw "Remote read-back failed for $file" }
}
Write-Output "T6 final files verified at $head"
