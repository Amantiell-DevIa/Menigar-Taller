#!/usr/bin/env node
/* Builds laboratorio.html from index.html: the same homepage, kept apart from the official one,
 * plus the review stylesheet and laboratorio.js, which swaps the hero designs in place.
 * Deriving it on every build keeps the lab identical to the homepage it is testing.
 * Usage: node scripts/build_laboratorio.cjs  (writes laboratorio.html next to index.html) */
'use strict';
const fs = require('fs');
const path = require('path');

function buildLaboratorio(indexHtml) {
  const steps = [
    [/<title>[^<]*<\/title>/, '<title>MENIGAR · Laboratorio de portada</title>'],
    [/<meta name="description" content="[^"]*">/, '<meta name="description" content="Página de revisión para comparar los diseños de la portada de MENIGAR. No es la web oficial.">'],
    [/(<link rel="stylesheet" href="\/assets\/css\/portada\.css">)/, '$1\n  <link rel="stylesheet" href="/assets/css/opciones-hero.css">'],
    [/(<script src="\/app\.js" defer><\/script>)/, '$1\n  <script src="/laboratorio.js" defer></script>'],
  ];
  return steps.reduce((html, [pattern, replacement]) => {
    if (!pattern.test(html)) throw new Error('index.html ya no contiene ' + pattern);
    return html.replace(pattern, replacement);
  }, indexHtml);
}

if (require.main === module) {
  const root = path.resolve(__dirname, '..');
  const html = buildLaboratorio(fs.readFileSync(path.join(root, 'index.html'), 'utf8'));
  fs.writeFileSync(path.join(root, 'laboratorio.html'), html);
  console.log('laboratorio.html generado desde index.html');
}

module.exports = { buildLaboratorio };
