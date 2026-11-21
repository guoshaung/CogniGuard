param([Parameter(Mandatory=$true)][int]$CompressorPid)
$ErrorActionPreference='Stop'
$afkRoot=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$afkOut=Join-Path $afkRoot 'var/results/hsw-st/afk_stage0_20261121'
$afkPython=Join-Path $afkRoot 'var/results/hsw-st/kosw_stage1_20261120/conda/envs/kosw/python.exe'
$env:PYTHONUTF8='1'
$env:OMP_NUM_THREADS='2'
while (-not (Test-Path -LiteralPath "$afkOut/quick_compression/C2/RESULT.json")) {
    $afkWorker=Get-CimInstance Win32_Process -Filter "ProcessId = $CompressorPid"
    if (-not $afkWorker -or $afkWorker.CommandLine -notmatch 'quick_compress.py') {
        throw 'Quick compression stopped before both local compressor result files; do not retry or substitute.'
    }
    Start-Sleep -Seconds 30
}
& $afkPython -u "$PSScriptRoot/report_quick.py"
if ($LASTEXITCODE -ne 0) {throw 'Offline report failed; preserve compression results'}
& $afkPython -c 'import json,hashlib;from pathlib import Path;p=Path(__import__("sys").argv[1]);r=Path(__import__("sys").argv[2]);names=["A0_RESULT.md","per_anchor.csv","figure_counts.json"];d={"status":"QUICK_GATE_COMPLETE_STAGE0_NOT_FULL_EVALUATION","public_sha256":{n:hashlib.sha256((p/n).read_bytes()).hexdigest() for n in names},"local_result_sha256":hashlib.sha256((r/"QUICK_RESULT.json").read_bytes()).hexdigest(),"paid_calls":0,"H2_calls":0};(p/"QUICK_RESULT_FREEZE.json").write_text(json.dumps(d,indent=2),encoding="utf8")' $PSScriptRoot $afkOut
if ($LASTEXITCODE -ne 0) {throw 'Result freezing failed'}
$afkFiles=@('A0_RESULT.md','per_anchor.csv','figure_counts.json','QUICK_RESULT_FREEZE.json') | ForEach-Object {"experiments/hsw_afk_stage0_20261121/$_"}
git -C $afkRoot add --sparse -- $afkFiles
if ($LASTEXITCODE -ne 0) {throw 'Result staging failed'}
git -C $afkRoot -c core.autocrlf=false commit -m 'Report AFK local two-compressor quick gate' --only -- $afkFiles
if ($LASTEXITCODE -ne 0) {throw 'Result commit failed'}
git -C $afkRoot push origin codex/hsw-st
if ($LASTEXITCODE -ne 0) {throw 'Result push failed'}
Write-Output 'AFK_QUICK_RESULT_PUBLISHED'
