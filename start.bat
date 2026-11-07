@echo off
setlocal
rem Double-click to send once; explicit arguments reuse deploy.bat actions.
if "%~1"=="" (
    call "%~dp0deploy.bat" run
) else (
    call "%~dp0deploy.bat" %*
)
set "START_EXIT_CODE=%ERRORLEVEL%"
if "%~1"=="" pause
exit /b %START_EXIT_CODE%
