@echo off
setlocal
set "PYTHONUTF8=1"
set "HF_HOME=%~dp0..\..\assets\models\kosw-hf-cache"
set "HF_HUB_OFFLINE=1"
set "TOKENIZERS_PARALLELISM=false"
set "OMP_NUM_THREADS=4"
set "MKL_NUM_THREADS=4"
set "KOSW_PY=%~dp0..\..\var\results\hsw-st\kosw_stage1_20261120\conda\envs\kosw\python.exe"
"%KOSW_PY%" -u "%~dp0run_stage1.py"
exit /b %ERRORLEVEL%
