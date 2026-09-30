#!/usr/bin/env bash
# Prueba de carga fija con Vegeta (Linux/Mac, con vegeta instalado).
# 50 req/s durante 30s rotando 4 PDFs. Correr desde tests/stress/.
set -e
RATE="${1:-50}"
DURATION="${2:-30s}"
TARGET="${3:-http://localhost/extract}"

TARGETS="vegeta/targets-generated.txt"
: > "$TARGETS"
for pdf in pdfs/01-liviano.pdf pdfs/02-chico.pdf pdfs/03-mediano.pdf pdfs/04-grande.pdf; do
  {
    echo "POST $TARGET"
    echo "Content-Type: application/pdf"
    echo "@$pdf"
    echo ""
  } >> "$TARGETS"
done

echo "Vegeta: $RATE req/s durante $DURATION contra $TARGET"
vegeta attack -targets="$TARGETS" -rate="$RATE" -duration="$DURATION" -timeout=30s \
  | tee vegeta/results.bin | vegeta report
