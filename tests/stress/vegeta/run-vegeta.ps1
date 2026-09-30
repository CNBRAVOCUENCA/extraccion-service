# Corre la prueba de carga fija de Vegeta con Docker (no instala Vegeta).
# Perfil del profesor: 50 req/s durante 30s (1500 solicitudes) rotando 4 PDFs.
# Ejecutar parada en la carpeta tests/stress:
#   Set-Location "C:\Users\Carito N\Desktop\micros\extraccion-service\tests\stress"
#   .\vegeta\run-vegeta.ps1
param(
    [ValidateRange(1, 5000)]
    [int]$Rate = 50,

    [ValidatePattern('^\d+(ms|s|m|h)$')]
    [string]$Duration = "30s",

    [string]$Target = "http://host.docker.internal/extract",

    [ValidatePattern('^\d+(ms|s|m|h)$')]
    [string]$Timeout = "30s"
)

$ErrorActionPreference = "Stop"
$stressDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

# Genera el archivo de targets rotando los 4 PDFs (body binario directo).
$pdfs = @(
    "pdfs/01-liviano.pdf",
    "pdfs/02-chico.pdf",
    "pdfs/03-mediano.pdf",
    "pdfs/04-grande.pdf"
)
$targetLines = @()
foreach ($pdf in $pdfs) {
    $targetLines += "POST $Target"
    $targetLines += "Content-Type: application/pdf"
    $targetLines += "@$pdf"
    $targetLines += ""
}
$targetsPath = Join-Path $stressDir "vegeta\targets-generated.txt"
[IO.File]::WriteAllLines($targetsPath, $targetLines, [Text.Encoding]::ASCII)

$resultsFile = "vegeta/extractor-$((Get-Date).ToString('yyyyMMdd-HHmmss')).bin"
Write-Host "Prueba Vegeta: $Rate req/s durante $Duration (timeout $Timeout) contra $Target"

& docker run --rm `
    --entrypoint vegeta `
    -v "${stressDir}:/work" `
    -w /work `
    peterevans/vegeta `
    attack "-targets=vegeta/targets-generated.txt" "-rate=$Rate" "-duration=$Duration" "-timeout=$Timeout" "-output=$resultsFile"
if ($LASTEXITCODE -ne 0) { throw "Vegeta terminó con error en el ataque." }

Write-Host "`nReporte:"
& docker run --rm `
    --entrypoint vegeta `
    -v "${stressDir}:/work" `
    -w /work `
    peterevans/vegeta `
    report "-type=text" $resultsFile

Write-Host "`nResultado guardado en: $(Join-Path $stressDir $resultsFile)"
