#!/usr/bin/env node
/* Static build for Vercel: copies only the public website into dist/.
 * Uses the same allowlist as scripts/build_review_package.py, so backend code,
 * private data, raw captures, tests and internal documents are never served.
 * The request form detects the missing API and stays as a design preview. */
'use strict';
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const out = path.join(root, 'dist');
const ROOT_FILES = ['index.html', 'servicios.html', 'solicitud.html', 'como-funciona.html', 'garantia.html', 'sobre-nosotros.html',
  'ayuda.html', 'privacidad.html', 'condiciones.html', 'cookies.html',
  'style.css', 'solicitud.css', 'hyundai.css', 'bmw.css', 'reparaciones.css', 'garantia.css', 'servicios.css', 'paginas.css',
  'app.js', 'solicitud.js', 'resumen.js', 'robots.txt', 'sitemap.xml', 'resumen.html', 'receipt.js', 'opciones-hero.html', 'laboratorio.js', 'laboratorio.html', 'favicon.ico', 'apple-touch-icon.png'];
const DATA_FILES = ['catalogo-v2.js', 'home-index.js', 'family-media.js'];
const ASSET_TYPES = new Set(['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.ico', '.pdf', '.css', '.woff2']);

let files = 0;
let bytes = 0;
function copy(relative) {
  const source = path.join(root, relative);
  if (!fs.statSync(source).isFile()) throw new Error('Missing file: ' + relative);
  const target = path.join(out, relative);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.copyFileSync(source, target);
  files += 1;
  bytes += fs.statSync(target).size;
}
function walk(relative, accept) {
  for (const entry of fs.readdirSync(path.join(root, relative), { withFileTypes: true })) {
    if (entry.name.startsWith('.')) continue;
    const child = path.join(relative, entry.name);
    if (entry.isDirectory()) walk(child, accept);
    else if (accept(child)) copy(child);
  }
}

fs.rmSync(out, { recursive: true, force: true });
// The lab page is rebuilt from index.html so a deploy always tests the current homepage.
fs.writeFileSync(path.join(root, 'laboratorio.html'), require('./build_laboratorio.cjs').buildLaboratorio(fs.readFileSync(path.join(root, 'index.html'), 'utf8')));
ROOT_FILES.forEach(copy);
DATA_FILES.forEach(name => copy(path.join('data', name)));
for (const entry of fs.readdirSync(path.join(root, 'reparaciones'), { withFileTypes: true })) {
  if (entry.isDirectory() && /^[A-Za-z0-9_-]+$/.test(entry.name)) copy(path.join('reparaciones', entry.name, 'index.html'));
}
walk('assets', file => ASSET_TYPES.has(path.extname(file).toLowerCase())
  || (file.startsWith(path.join('assets', 'fonts')) && /^LICENSE.*\.txt$/.test(path.basename(file))));
console.log(`dist/: ${files} archivos, ${(bytes / 1e6).toFixed(1)} MB`);
