# 在 CogniGuard 仓库的 .venv 中安装 GPU 版 PyTorch（Windows / PowerShell）
#
# 用法（任意目录执行均可，脚本会向上查找 .venv）:
#   powershell -ExecutionPolicy Bypass -File "D:\pycharm\CogniGuard\protection\audit_trace\scripts\install_pytorch_cuda.ps1"
#
# 注意:
# - .venv 在仓库根 CogniGuard\.venv，不在 protection/audit_trace\.venv；不要 cd 到子目录后执行 .\.venv\...
# - SSL / UNEXPECTED_EOF 常见于系统代理（http_proxy）或公司 MITM，脚本会先清空代理再装
# - 驱动 528.x 建议 cu121；驱动约 560+ 可改用 cu126（见文末注释）

$ErrorActionPreference = "Stop"

function Find-VenvPip {
    $dir = $PSScriptRoot
    while ($dir) {
        $c = Join-Path $dir ".venv\Scripts\pip.exe"
        if (Test-Path $c) { return $c }
        $parent = Split-Path $dir -Parent
        if ($parent -eq $dir) { break }
        $dir = $parent
    }
    return $null
}

$pip = Find-VenvPip
if (-not $pip) {
    Write-Host "错误: 从脚本目录向上找不到 .venv\Scripts\pip.exe"
    Write-Host "请确认已创建: D:\pycharm\CogniGuard\.venv"
    exit 1
}

$py = Join-Path (Split-Path $pip -Parent) "python.exe"
Write-Host "pip: $pip"

# 代理常导致访问 download-r2.pytorch.org 时 SSL 中途断开
Write-Host "临时清除 HTTP(S) 代理环境变量（仅当前窗口）..."
foreach ($k in @(
    "HTTP_PROXY","HTTPS_PROXY","ALL_PROXY","http_proxy","https_proxy","all_proxy",
    "NO_PROXY","no_proxy"
)) { Remove-Item "Env:$k" -ErrorAction SilentlyContinue }

Write-Host "尝试安装 torch 2.5.1 + CUDA 12.1（cu121）..."
$args = @(
    "install", "--upgrade", "--no-cache-dir",
    "torch==2.5.1+cu121", "torchvision==0.20.1+cu121", "torchaudio==2.5.1+cu121",
    "--index-url", "https://download.pytorch.org/whl/cu121",
    "--trusted-host", "download.pytorch.org",
    "--trusted-host", "download-r2.pytorch.org"
)
& $pip @args
$pipOk = $LASTEXITCODE -eq 0

& $py -c "import torch; print('torch', torch.__version__); print('cuda', torch.cuda.is_available())" 2>$null
$torchOk = $LASTEXITCODE -eq 0

if (-not $pipOk -or -not $torchOk) {
    Write-Host "GPU 版安装失败或未导入 torch，正在回退安装 PyPI 上的 CPU 版（保证能 import）..."
    & $pip install --upgrade "torch>=2.5.0"
    & $py -c "import torch; print('torch', torch.__version__); print('cuda', torch.cuda.is_available())"
}

Write-Host "完成。若 cuda 仍为 False：检查本机是否仍走代理、或用手机热点重试本脚本；或浏览器下载 whl 后:"
Write-Host "  $pip install C:\path\to\torch-2.5.1+cu121-cp312-cp312-win_amd64.whl"

# --- 可选：驱动升级到约 560+ 后改用 CUDA 12.6 + torch 2.11 ---
# 清空代理后执行:
# & $pip install --upgrade torch==2.11.0+cu126 torchvision torchaudio --index-url https://download.pytorch.org/whl/cu126 --trusted-host download.pytorch.org --trusted-host download-r2.pytorch.org
