'use strict';
/* Compare the real guided-search controller with the full and small data files.
 * It verifies every offered brand, every model for each brand, and every family
 * after the same selections; no copy of app.js filtering rules is used here.
 */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '..');
const application = fs.readFileSync(path.join(root, 'app.js'), 'utf8');

function fixture(dataFile) {
  class Element {
    constructor() {
      this.value = ''; this.options = []; this.hidden = false; this.innerHTML = '';
      this.textContent = ''; this.events = new Map(); this.attributes = {};
      this.classList = {toggle() {}};
    }
    replaceChildren(...items) { this.options = items; this.value = items[0]?.value || ''; }
    add(option) { this.options.push(option); if (option.selected) this.value = option.value; }
    addEventListener(name, callback) { this.events.set(name, callback); }
    emit(name) { this.events.get(name)?.({preventDefault() {}}); }
    setAttribute(name, value) { this.attributes[name] = value; }
    removeAttribute(name) { delete this.attributes[name]; }
    focus() {}
  }
  const nodes = new Map();
  const element = id => { if (!nodes.has(id)) nodes.set(id, new Element()); return nodes.get(id); };
  const stages = [new Element(), new Element(), new Element()];
  const indicators = [new Element(), new Element(), new Element()];
  const form = element('guided-search-form');
  const controls = Object.fromEntries(['back', 'skip', 'next', 'submit'].map(name => [name, new Element()]));
  form.querySelectorAll = selector => selector === '[data-guide-stage]' ? stages : [];
  form.querySelector = selector => controls[selector.match(/data-guide-(\w+)/)?.[1]] || null;
  ['guide-brand', 'guide-model', 'guide-component', 'guide-summary'].forEach(element);
  const document = {
    querySelector() { return null; },
    querySelectorAll(selector) { return selector === '[data-guide-indicator]' ? indicators : []; },
    getElementById(id) { return nodes.get(id) || null; }
  };
  const context = {
    window: {}, document,
    location: {hostname:'tests.example', assign() {}},
    console, Intl, URLSearchParams, Map, Set, Date,
    Option: function Option(label, value, _default, selected) {
      this.label = label; this.value = value; this.selected = selected;
    }
  };
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(path.join(root, dataFile), 'utf8'), context, {filename:dataFile});
  vm.runInContext(application, context, {filename:'app.js'});
  return {window:context.window, element};
}

function entries(select) {
  return Array.from(select.options, option => [option.value, option.label]);
}

const full = fixture('data/catalogo-v2.js');
const home = fixture('data/home-index.js');
assert.deepEqual(JSON.parse(JSON.stringify(home.window.MENIGAR_FAMILIES)), JSON.parse(JSON.stringify(full.window.MENIGAR_FAMILIES)));
assert.deepEqual(entries(home.element('guide-brand')), entries(full.element('guide-brand')));
assert.deepEqual(entries(home.element('guide-model')), entries(full.element('guide-model')));
assert.deepEqual(entries(home.element('guide-component')), entries(full.element('guide-component')));

// The homepage is simple (owner, 22 Oct 2026): two ways to start, no finder and no family grid.
// Way 1 searches a fault code or reference on servicios.html; way 2 opens its step-by-step filters.
const homepage = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
const ways = homepage.match(/<ol class="p-ways"[\s\S]*?<\/ol>/)?.[0] || '';
assert.equal((ways.match(/<li class="p-way/g) || []).length, 2, 'El hero ofrece exactamente dos maneras de empezar.');
assert.match(ways, /<form class="p-search" action="\/servicios\.html" method="get" role="search">[\s\S]*?name="q"[^>]*required/, 'La primera manera busca el código o la referencia en servicios.');
assert.match(ways, /href="\/servicios\.html#catalogo"/, 'La segunda manera abre la búsqueda paso a paso de servicios.');
assert.ok(!/id="buscar"|id="que-reparamos"|home-index\.js/.test(homepage), 'La portada ya no incluye el buscador ni la rejilla de familias.');
assert.match(homepage, /Laboratorio · archivo 2017/);
// The hero shows three real pieces, each named (owner, 23 Oct 2026), and the header carries MENIGAR's
// own logo; every responsive image candidate exists.
const pieces = [...homepage.matchAll(/<figure class="p-piece p-piece--(\w+)">[\s\S]*?<figcaption>[^<]+<\/figcaption><\/figure>/g)].map(match => match[1]);
assert.deepEqual(pieces, ['cuadro', 'pantalla', 'abs'], 'El hero muestra cuadro, pantalla y módulo ABS, cada uno con su nombre.');
assert.match(homepage, /<header class="site-header">[\s\S]*?<img class="brand-logo" src="\/assets\/marca\/menigar-logo-1x\.webp"/, 'La cabecera usa el logo de MENIGAR.');
for (const [, set] of homepage.matchAll(/srcset="([^"]+)"/g)) {
  for (const candidate of set.split(',')) {
    const src = candidate.trim().split(/\s+/)[0];
    assert.ok(fs.existsSync(path.join(root, src)), `Falta la imagen ${src}`);
  }
}

// Videos and the map are click-to-load: the page itself never contains a
// third-party frame, and each placeholder keeps a plain link that works
// without JavaScript. The CSP must allow exactly the two player hosts.
for (const page of ['index.html', 'opciones-hero.html']) {
  const html = fs.readFileSync(path.join(root, page), 'utf8');
  assert.ok(!/<iframe/i.test(html), `${page} no carga marcos de terceros al abrirse.`);
  for (const [, src] of html.matchAll(/<img [^>]*src="([^"]+)"/g)) {
    assert.ok(fs.existsSync(path.join(root, src)), `${page}: falta la imagen ${src}`);
  }
}
const videos = [...homepage.matchAll(/data-embed="youtube" data-embed-src="([^"]+)"[\s\S]*?href="https:\/\/www\.youtube\.com\/watch\?v=([^"]+)"/g)];
assert.equal(videos.length, 3, 'La portada muestra tres vídeos del canal.');
for (const [, id, link] of videos) {
  assert.match(id, /^[\w-]{11}$/, `Identificador de vídeo válido: ${id}`);
  assert.equal(link, id, 'El enlace sin JavaScript abre el mismo vídeo.');
}
assert.match(homepage, /data-embed="map" data-embed-src="https:\/\/www\.google\.com\/maps\/embed\?pb=[\w!%.-]+"/, 'El mapa usa la inserción oficial de Google Maps.');
assert.match(homepage, /href="https:\/\/maps\.app\.goo\.gl\/[\w]+"/, 'La ubicación también se abre en Google Maps sin cargar el mapa.');
const csp = JSON.parse(fs.readFileSync(path.join(root, 'vercel.json'), 'utf8')).headers[0].headers.find(header => header.key === 'Content-Security-Policy').value;
assert.match(csp, /frame-src https:\/\/www\.youtube-nocookie\.com https:\/\/www\.google\.com;/, 'La CSP de Vercel permite solo los dos reproductores.');
assert.match(csp, /script-src 'self';/, 'La CSP sigue sin scripts de terceros.');

// The Google rating is recognisable at a glance: Google's G sits on the hero
// chip and on the score card, decorative for screen readers (the text says Google).
for (const where of [/class="p-rating p-hero-rating" href="#opiniones"><span class="p-g" aria-hidden="true">/, /class="p-score-label"><span class="p-g p-g--lg" aria-hidden="true">/]) {
  assert.match(homepage, where, 'La valoración de Google lleva la G de Google.');
}

// The review lab is a page of its own, apart from the official homepage: the
// homepage and app.js carry nothing of it, and laboratorio.html is the homepage
// itself plus the lab stylesheet and script, rebuilt from index.html.
assert.ok(!/lab-panel|laboratorio\.(?:js|html)|opciones-hero\.css/.test(homepage), 'La portada oficial no incluye el laboratorio.');
assert.ok(!/laboratorio\.(?:js|html)|setupLab/.test(application), 'app.js no carga el laboratorio en ninguna página.');
const { buildLaboratorio } = require(path.join(root, 'scripts/build_laboratorio.cjs'));
const labPage = fs.readFileSync(path.join(root, 'laboratorio.html'), 'utf8');
assert.equal(labPage, buildLaboratorio(homepage), 'laboratorio.html está al día con index.html: ejecuta node scripts/build_laboratorio.cjs.');
assert.match(labPage, /<script src="\/laboratorio\.js" defer><\/script>/, 'La página del laboratorio carga su script.');
const vercelBuild = fs.readFileSync(path.join(root, 'scripts/build_vercel_static.cjs'), 'utf8');
for (const file of ['laboratorio.html', 'laboratorio.js', 'opciones-hero.html']) {
  assert.ok(fs.existsSync(path.join(root, file)) && vercelBuild.includes(`'${file}'`), `${file} existe y se publica en Vercel.`);
}
const lab = fs.readFileSync(path.join(root, 'laboratorio.js'), 'utf8');
assert.ok(!/Copiar enlace|Qué es/.test(lab), 'El panel del laboratorio no muestra «Qué es» ni «Copiar enlace».');
const options = fs.readFileSync(path.join(root, 'opciones-hero.html'), 'utf8');
for (const key of ['a', 'b', 'c', 'd']) {
  assert.match(options, new RegExp(`id="opcion-${key}"[\\s\\S]*?class="p-hero`), `La página de opciones aporta el diseño ${key.toUpperCase()} al laboratorio.`);
}
for (const palette of ['cobalto', 'cian', 'violeta', 'noche']) assert.ok(lab.includes(`'${palette}'`), `El laboratorio ofrece el fondo ${palette}.`);

let modelsChecked = 0;
const brandOptions = entries(full.element('guide-brand'));
for (const [brand] of brandOptions) {
  for (const view of [full, home]) {
    view.element('guide-brand').value = brand;
    view.element('guide-brand').emit('change');
  }
  const models = entries(full.element('guide-model'));
  assert.deepEqual(entries(home.element('guide-model')), models, `Modelos para ${brand || 'todas las marcas'}`);
  assert.deepEqual(entries(home.element('guide-component')), entries(full.element('guide-component')), `Familias para ${brand || 'todas las marcas'}`);
  for (const [model] of models) {
    for (const view of [full, home]) {
      view.element('guide-model').value = model;
      view.element('guide-model').emit('change');
    }
    assert.deepEqual(entries(home.element('guide-component')), entries(full.element('guide-component')), `Familias para ${brand || 'todas las marcas'} / ${model || 'sin modelo'}`);
    modelsChecked += 1;
  }
}
console.log(`Índice de inicio equivalente: ${brandOptions.length - 1} marcas, ${modelsChecked} opciones de modelo y sus familias.`);
