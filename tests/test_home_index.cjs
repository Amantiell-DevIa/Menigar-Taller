'use strict';
/* The homepage (index.html) after the owner's mockup, and the videos and map of Sobre nosotros,
 * which load only when the visitor asks for them.
 */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');

// The homepage follows the owner's mockup (28 Oct 2026): one search on /servicios/, the step-by-step
// link, the six specialties and three steps. Videos, reviews and the map moved to Sobre nosotros.
const homepage = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
assert.match(homepage, /<form class="h-search" action="\/servicios\/" method="get" role="search">[\s\S]*?name="q"[^>]*required/, 'La portada busca el código, la referencia o el modelo en servicios.');
assert.match(homepage, /href="\/servicios\/#catalogo"/, 'La búsqueda paso a paso sigue a un clic.');
assert.ok(!/id="buscar"|id="que-reparamos"|home-index\.js/.test(homepage), 'La portada no carga el buscador antiguo.');
const pieces = [...homepage.matchAll(/<figure class="h-piece h-piece--(\w+)">/g)].map(match => match[1]);
assert.deepEqual(pieces, ['cuadro', 'pantalla', 'abs'], 'El hero muestra cuadro, pantalla y módulo ABS.');
assert.match(homepage, /<header class="site-header">[\s\S]*?<img class="brand-logo" src="\/assets\/marca\/menigar-logo-1x\.webp"/, 'La cabecera usa el logo de MENIGAR.');
for (const [, set] of homepage.matchAll(/srcset="([^"]+)"/g)) {
  for (const candidate of set.split(',')) {
    const src = candidate.trim().split(/\s+/)[0];
    assert.ok(fs.existsSync(path.join(root, src)), `Falta la imagen ${src}`);
  }
}

// Videos and the map are click-to-load: no page contains a third-party frame on arrival, and each
// placeholder keeps a plain link that works without JavaScript. The CSP allows exactly the two players.
const about = fs.readFileSync(path.join(root, 'sobre-nosotros/index.html'), 'utf8');
for (const page of ['index.html', 'sobre-nosotros/index.html']) {
  const html = fs.readFileSync(path.join(root, page), 'utf8');
  assert.ok(!/<iframe/i.test(html), `${page} no carga marcos de terceros al abrirse.`);
  for (const [, src] of html.matchAll(/<img [^>]*src="([^"]+)"/g)) {
    assert.ok(fs.existsSync(path.join(root, src)), `${page}: falta la imagen ${src}`);
  }
}
const videos = [...about.matchAll(/data-embed="youtube" data-embed-src="([^"]+)"[\s\S]*?href="https:\/\/www\.youtube\.com\/watch\?v=([^"]+)"/g)];
assert.equal(videos.length, 3, 'Sobre nosotros muestra tres vídeos del canal.');
for (const [, id, link] of videos) {
  assert.match(id, /^[\w-]{11}$/, `Identificador de vídeo válido: ${id}`);
  assert.equal(link, id, 'El enlace sin JavaScript abre el mismo vídeo.');
}
assert.match(about, /data-embed="map" data-embed-src="https:\/\/www\.google\.com\/maps\/embed\?pb=[\w!%.-]+"/, 'El mapa usa la inserción oficial de Google Maps.');
assert.match(about, /href="https:\/\/maps\.app\.goo\.gl\/[\w]+"/, 'La ubicación también se abre en Google Maps sin cargar el mapa.');
const csp = JSON.parse(fs.readFileSync(path.join(root, 'vercel.json'), 'utf8')).headers[0].headers.find(header => header.key === 'Content-Security-Policy').value;
assert.match(csp, /frame-src https:\/\/www\.youtube-nocookie\.com https:\/\/www\.google\.com;/, 'La CSP de Vercel permite solo los dos reproductores.');
assert.match(csp, /script-src 'self';/, 'La CSP sigue sin scripts de terceros.');

// The Google rating is recognisable at a glance: Google's G sits on the homepage rating and on the score
// card of Sobre nosotros, decorative for screen readers (the text says Google).
assert.match(homepage, /<p class="h-rating"><span class="h-g" aria-hidden="true">/, 'La valoración de la portada lleva la G de Google.');
assert.match(about, /class="p-score-label"><span class="p-g p-g--lg" aria-hidden="true">/, 'La tarjeta de valoración lleva la G de Google.');

console.log('Portada y Sobre nosotros: comprobaciones superadas.');
