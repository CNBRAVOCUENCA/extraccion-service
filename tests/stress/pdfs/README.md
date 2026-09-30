# Set de PDFs de prueba

Estos 4 PDFs de tamaño variable se usan en las pruebas de carga (Vegeta y k6),
rotándolos en cada petición, según pide el TP:

| Archivo          | Tamaño aprox. |
|------------------|---------------|
| 01-liviano.pdf   | ~170 KB       |
| 02-chico.pdf     | ~290 KB       |
| 03-mediano.pdf   | ~1,3 MB       |
| 04-grande.pdf    | ~2,5 MB       |

Si querés acercarte más al set del profesor (que incluye un PDF pesado de ~9 MB
con gráficos/capas), agregá uno como `05-pesado.pdf` y sumalo a la lista de
`run-vegeta.ps1` y `spike.js`.
