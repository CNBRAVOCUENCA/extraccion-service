// Prueba Spike con k6 (modelo cerrado) — reproduce el perfil del profesor:
//   rampa a 100 VUs en 10s, 20s sostenidos a 100 VUs, rampa a 0 en 10s.
//
// Cada iteración rota los PDFs configurados y verifica HTTP 200.
//
// Correr (con Docker, sin instalar k6):
//   docker run --rm -i -v "${PWD}:/work" -w /work grafana/k6 run k6/spike.js
// o con la variable de destino:
//   docker run --rm -i -e TARGET=http://host.docker.internal/extract -v "${PWD}:/work" -w /work grafana/k6 run k6/spike.js

import http from 'k6/http';
import { check } from 'k6';

// open() debe ir en el init (fuera de la función default). 'b' = binario.
const PDFS = [];
if (__ENV.ONLY_ADDITIONAL_PDF !== 'true') {
  PDFS.push(
    open('../pdfs/01-liviano.pdf', 'b'),
    open('../pdfs/02-chico.pdf', 'b'),
    open('../pdfs/03-mediano.pdf', 'b'),
    open('../pdfs/04-grande.pdf', 'b'),
  );
}
if (__ENV.ADDITIONAL_PDF === 'true') {
  PDFS.push(open('/extra/05-adicional-local.pdf', 'b'));
}

const TARGET = __ENV.TARGET || 'http://gateway/extract';

export const options = {
  scenarios: {
    spike: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '10s', target: 100 },
        { duration: '20s', target: 100 },
        { duration: '10s', target: 0 },
      ],
      gracefulStop: '30s',
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.05'], // objetivo: menos de 5% de error
  },
};

export default function () {
  const idx = (__VU + __ITER) % PDFS.length;
  const payload = { file: http.file(PDFS[idx], `doc-${idx}.pdf`, 'application/pdf') };
  const res = http.post(TARGET, payload, { timeout: '30s' });
  check(res, {
    'status 200': (r) => r.status === 200,
  });
}
