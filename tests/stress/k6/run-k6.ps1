# Corre la prueba Spike de k6 con Docker (no hace falta instalar k6).
# k6 corre dentro de la red del stack y le pega directo al gateway (nginx).
# Uso (desde cualquier carpeta):
#   & "C:\Users\Carito N\Desktop\micros\extraccion-service\tests\stress\k6\run-k6.ps1"
param(
    [string]$Network = "extractor-stress_web",
    [string]$Target = "http://gateway/extract"
)

$ErrorActionPreference = "Stop"
$stressDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

& docker network inspect $Network *> $null
if ($LASTEXITCODE -ne 0) {
    throw "No existe la red '$Network'. Levanta el stack primero: docker compose up -d --build (en extraccion-service)."
}

$summaryFile = "k6/resultado-$((Get-Date).ToString('yyyyMMdd-HHmmss')).txt"
Write-Host "Prueba Spike (k6) contra $Target"
# k6 escribe el progreso por stderr: que no se interprete como error de PowerShell.
$ErrorActionPreference = "Continue"
& docker run --rm -i `
    --network $Network `
    -e "TARGET=$Target" `
    -v "${stressDir}:/work" `
    -w /work `
    grafana/k6 run --no-color k6/spike.js 2>&1 | Tee-Object -FilePath (Join-Path $stressDir $summaryFile)

Write-Host "`nResumen guardado en: $(Join-Path $stressDir $summaryFile)"
