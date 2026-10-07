# Corre la prueba de carga fija de Vegeta con Docker (no instala Vegeta).
# Perfil del profesor: 50 req/s durante 30s (1500 solicitudes) rotando 4 PDFs.
#
# Vegeta corre DENTRO de la red de Docker del stack y le pega directo al
# gateway (nginx). Así no depende de host.docker.internal ni del puerto 80
# del host de Windows.
#
# Requisito: el stack levantado (docker compose up -d --build en extraccion-service).
# Uso (desde cualquier carpeta):
#   & "C:\Users\Carito N\Desktop\micros\extraccion-service\tests\stress\vegeta\run-vegeta.ps1"
param(
    [ValidateRange(1, 5000)]
    [int]$Rate = 50,

    [ValidatePattern('^\d+(ms|s|m|h)$')]
    [string]$Duration = "30s",

    [ValidatePattern('^\d+(ms|s|m|h)$')]
    [string]$Timeout = "30s",

    [string]$Network = "extractor-stress_web",

    [string]$Target = "http://gateway/extract",

    [string]$AdditionalPdfPath,

    [switch]$OnlyAdditionalPdf
)

$ErrorActionPreference = "Stop"
$stressDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$extraPdfName = "05-adicional-local.pdf"
$mountArguments = @("--volume", "${stressDir}:/work")
$preflightPdf = "/work/pdfs/04-grande.pdf"

if ($OnlyAdditionalPdf -and [string]::IsNullOrWhiteSpace($AdditionalPdfPath)) {
    throw "-OnlyAdditionalPdf requiere -AdditionalPdfPath."
}

if (-not [string]::IsNullOrWhiteSpace($AdditionalPdfPath)) {
    if (-not (Test-Path -LiteralPath $AdditionalPdfPath -PathType Leaf)) {
        throw "No se encontro el PDF adicional: $AdditionalPdfPath"
    }
    $extraPdfPath = (Resolve-Path -LiteralPath $AdditionalPdfPath).Path
    if ([IO.Path]::GetExtension($extraPdfPath) -ine ".pdf") {
        throw "El archivo adicional debe tener extension .pdf."
    }
    $mountArguments += @(
        "--mount",
        "type=bind,source=$extraPdfPath,target=/extra/$extraPdfName,readonly"
    )
    $preflightPdf = "/extra/$extraPdfName"
}

# 0) La red del stack tiene que existir (stack levantado).
& docker network inspect $Network *> $null
if ($LASTEXITCODE -ne 0) {
    throw "No existe la red '$Network'. Levanta el stack primero: docker compose up -d --build (en extraccion-service)."
}

# 1) Chequeo previo: UNA petición real con el PDF más grande, para ver el
#    código HTTP antes de disparar las 1500.
Write-Host "Chequeo previo: POST $Target con $preflightPdf ..."
$check = & docker run --rm --network $Network @mountArguments curlimages/curl `
    -s -o /dev/null -w "%{http_code}" `
    -H "Content-Type: application/pdf" `
    --data-binary "@$preflightPdf" `
    $Target
Write-Host "  -> HTTP $check"
if ($check -ne "200") {
    throw "El chequeo previo devolvió HTTP $check (se esperaba 200). Revisá: docker compose ps  y  docker compose logs --tail=30 gateway extractor"
}

# 2) Targets rotando el corpus base o solo el PDF externo.
if ($OnlyAdditionalPdf) {
    $pdfs = @($preflightPdf)
    Write-Host "Prueba exclusiva con el PDF local: $extraPdfName"
}
else {
    $pdfs = @(
        "pdfs/01-liviano.pdf",
        "pdfs/02-chico.pdf",
        "pdfs/03-mediano.pdf",
        "pdfs/04-grande.pdf"
    )
}
if (-not $OnlyAdditionalPdf -and -not [string]::IsNullOrWhiteSpace($AdditionalPdfPath)) {
    $pdfs += $preflightPdf
    Write-Host "Se agrega PDF local adicional: $extraPdfName"
}
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
$resultsContainerPath = "/tmp/$([IO.Path]::GetFileName($resultsFile))"
$attackContainer = "vegeta-attack-$([guid]::NewGuid().ToString('N'))"
Write-Host "Prueba Vegeta: $Rate req/s durante $Duration (timeout $Timeout) contra $Target"

try {
    & docker run --name $attackContainer `
    --network $Network `
    --entrypoint vegeta `
    @mountArguments `
    -w /work `
    peterevans/vegeta `
    attack "-targets=vegeta/targets-generated.txt" "-rate=$Rate" "-duration=$Duration" "-timeout=$Timeout" "-output=$resultsContainerPath"
    if ($LASTEXITCODE -ne 0) { throw "Vegeta terminó con error en el ataque." }

    & docker cp "${attackContainer}:$resultsContainerPath" (Join-Path $stressDir $resultsFile)
    if ($LASTEXITCODE -ne 0) { throw "No se pudo copiar el resultado de Vegeta al directorio del proyecto." }
}
finally {
    & docker rm -f $attackContainer *> $null
}

Write-Host "`nReporte:"
& docker run --rm `
    --entrypoint vegeta `
    -v "${stressDir}:/work" `
    -w /work `
    peterevans/vegeta `
    report "-type=text" $resultsFile

Write-Host "`nResultado guardado en: $(Join-Path $stressDir $resultsFile)"
