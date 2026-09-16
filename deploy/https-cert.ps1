# HTTPS-сертификат для локальной/внутренней сети через mkcert
# Использование: powershell -ExecutionPolicy Bypass -File https-cert.ps1 -Domain "mesh.local"
param(
    [string]$Domain = "localhost"
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command mkcert -ErrorAction SilentlyContinue)) {
    Write-Host "Установите mkcert: winget install --id FiloSottile.mkcert" 
    exit 1
}

mkcert -install
mkcert $Domain

$certFile = Join-Path $PSScriptRoot "$Domain.pem"
$keyFile = Join-Path $PSScriptRoot "$Domain-key.pem"

Write-Host ""
Write-Host "Сертификат готов:"
Write-Host "  cert: $certFile"
Write-Host "  key:  $keyFile"
Write-Host ""
Write-Host "Чтобы uvicorn слушал HTTPS, запустите:"
Write-Host "  py -3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --ssl-keyfile $keyFile --ssl-certfile $certFile"
Write-Host "Или настройте реверс-прокси (nginx/caddy) для терминирования TLS."