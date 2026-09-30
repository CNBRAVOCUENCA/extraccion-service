# Corre la prueba Spike de k6 con Docker (no hace falta instalar k6).
# Ejecutar parada en la carpeta tests/stress:
#   Set-Location "C:\Users\Carito N\Desktop\micros\extraccion-service\tests\stress"
#   .\k6\run-k6.ps1
param(
    [string]$Target = "http://host.docker.internal/extract"
)

$ErrorActionPreference = "Stop"
$stressDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

Write-Host "Prueba Spike (k6) contra $Target"
& docker run --rm -i `
    -e "TARGET=$Target" `
    -v "${stressDir}:/work" `
    -w /work `
    grafana/k6 run k6/spike.js
