@echo off
setlocal
rem Prevent PowerShell 7 module paths from leaking through cmd into Windows PowerShell.
set "PSModulePath="
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0deploy.ps1" %*
set "DEPLOY_EXIT_CODE=%ERRORLEVEL%"
if "%~1"=="" pause
exit /b %DEPLOY_EXIT_CODE%
