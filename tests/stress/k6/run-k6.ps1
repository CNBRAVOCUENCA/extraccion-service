# Corre la prueba Spike de k6 con Docker (no hace falta instalar k6).
# k6 corre dentro de la red del stack y le pega directo al gateway (nginx).
# Uso (desde cualquier carpeta):
#   & "C:\Users\Carito N\Desktop\micros\extraccion-service\tests\stress\k6\run-k6.ps1"
param(
    [string]$Network = "extractor-stress_web",
    [string]$Target = "http://gateway/extract",
    [string]$AdditionalPdfPath,
    [switch]$OnlyAdditionalPdf
)

$ErrorActionPreference = "Stop"
$stressDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

if ($OnlyAdditionalPdf -and [string]::IsNullOrWhiteSpace($AdditionalPdfPath)) {
    throw "-OnlyAdditionalPdf requiere -AdditionalPdfPath."
}

& docker network inspect $Network *> $null
if ($LASTEXITCODE -ne 0) {
    throw "No existe la red '$Network'. Levanta el stack primero: docker compose up -d --build (en extraccion-service)."
}

$summaryFile = "k6/resultado-$((Get-Date).ToString('yyyyMMdd-HHmmss')).txt"
Write-Host "Prueba Spike (k6) contra $Target"
$dockerArguments = @(
    "run", "--rm", "-i",
    "--network", $Network,
    "-e", "TARGET=$Target",
    "-v", "${stressDir}:/work",
    "-e", "ONLY_ADDITIONAL_PDF=$($OnlyAdditionalPdf.IsPresent.ToString().ToLowerInvariant())"
)

if (-not [string]::IsNullOrWhiteSpace($AdditionalPdfPath)) {
    if (-not (Test-Path -LiteralPath $AdditionalPdfPath -PathType Leaf)) {
        throw "No se encontro el PDF adicional: $AdditionalPdfPath"
    }
    $extraPdfPath = (Resolve-Path -LiteralPath $AdditionalPdfPath).Path
    if ([IO.Path]::GetExtension($extraPdfPath) -ine ".pdf") {
        throw "El archivo adicional debe tener extension .pdf."
    }
    $dockerArguments += @(
        "-e", "ADDITIONAL_PDF=true",
        "--mount", "type=bind,source=$extraPdfPath,target=/extra/05-adicional-local.pdf,readonly"
    )
    Write-Host "Se agrega PDF local adicional: $extraPdfPath"
}

$dockerArguments += @("-w", "/work", "grafana/k6", "run", "--no-color", "k6/spike.js")
# k6 escribe el progreso por stderr: que no se interprete como error de PowerShell.
$ErrorActionPreference = "Continue"
& docker @dockerArguments 2>&1 | Tee-Object -FilePath (Join-Path $stressDir $summaryFile)
$dockerExitCode = $LASTEXITCODE

Write-Host "`nResumen guardado en: $(Join-Path $stressDir $summaryFile)"
if ($dockerExitCode -ne 0) {
    throw "k6 termino con error (exit code $dockerExitCode)."
}
