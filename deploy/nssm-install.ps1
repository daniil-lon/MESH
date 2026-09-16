# Установка МЭШ Колледж как Windows-сервиса через NSSM
# Использование: powershell -ExecutionPolicy Bypass -File nssm-install.ps1
param(
    [string]$AppPath = "C:\mesh-college",
    [string]$PythonPath = "py"
)

$ErrorActionPreference = "Stop"
$nssm = Join-Path $PSScriptRoot "nssm.exe"
$service = "mesh-college"

if (-not (Test-Path $nssm)) {
    Write-Host "Скачайте nssm (https://nssm.cc) и положите nssm.exe рядом с этим скриптом"
    exit 1
}

$python = (Get-Command $PythonPath -ErrorAction SilentlyContinue).Source
if (-not $python) {
    Write-Host "Python не найден. Укажите -PythonPath, например: py -3"
    exit 1
}

& $nssm install $service $python "-3 -X utf8 backend\main.py"
& $nssm set $service AppDirectory $AppPath
& $nssm set $service AppStdout (Join-Path $AppPath "backend\service.log")
& $nssm set $service AppStderr (Join-Path $AppPath "backend\service.log")
& $nssm set $service AppRotateFiles 1
& $nssm set $service Start SERVICE_AUTO_START
& $nssm restart $service

Write-Host "Сервис $service установлен и запущен."
Write-Host "Управление: nssm start/stop/restart $service, nssm edit $service"