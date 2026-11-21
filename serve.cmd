@echo off
setlocal
set "PYTHONUTF8=1"
set "PYTHONPATH=%~dp0;%PYTHONPATH%"
set "PYTHONPYCACHEPREFIX=%~dp0var\cache\python"
set "CG_PY=%~dp0.venv-langgraph\Scripts\python.exe"
if not exist "%CG_PY%" (
  echo LangGraph runtime missing. Install requirements.txt into .venv-langgraph first. 1>&2
  exit /b 1
)
"%CG_PY%" -m cogniguard.api %*
exit /b %ERRORLEVEL%
