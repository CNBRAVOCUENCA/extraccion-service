# Set de PDFs de prueba

Estos 4 PDFs de tamaño variable son el corpus base local de las pruebas de carga
(Vegeta y k6), rotándolos en cada petición:

| Archivo          | Tamaño aprox. |
|------------------|---------------|
| 01-liviano.pdf   | ~170 KB       |
| 02-chico.pdf     | ~290 KB       |
| 03-mediano.pdf   | ~1,3 MB       |
| 04-grande.pdf    | ~2,5 MB       |

El libro usado como prueba adicional no se copia a esta carpeta ni se versiona.
Se pasa a los dos scripts mediante `-AdditionalPdfPath`; Docker lo monta como
`/extra/05-adicional-local.pdf` en solo lectura, fuera del volumen del repositorio.
Es un caso adicional y no reemplaza el corpus oficial de la catedra.
