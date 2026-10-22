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

// The homepage presents every family before JavaScript runs. Keep its links
// aligned with the same generated family list used by guided search.
const homepage = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
const featuredLinks = [...homepage.matchAll(/class="home-family" href="\/servicios\.html\?pieza=([a-z]+)"/g)].map(match => match[1]);
const otherLinks = [...homepage.matchAll(/class="home-family-link" href="\/servicios\.html\?pieza=([a-z]+)"/g)].map(match => match[1]);
const familyKeys = Array.from(home.window.MENIGAR_FAMILIES, family => family.key);
assert.deepEqual(featuredLinks, familyKeys.slice(0, 4), 'Las cuatro familias destacadas de portada conservan las familias principales.');
assert.deepEqual(otherLinks, familyKeys.slice(4), 'Todos los servicios restantes tienen un enlace HTML inicial.');
const mediaContext = {window:{}};
vm.runInNewContext(fs.readFileSync(path.join(root, 'data/family-media.js'), 'utf8'), mediaContext);
// Featured families are illustrated; any photograph placed there must keep its documented source.
const featuredMarkup = homepage.match(/<div class="home-family-grid">([\s\S]*?)<\/div>/)?.[1] || '';
assert.ok(featuredMarkup.includes('class="home-family"'), 'La rejilla de familias destacadas está presente.');
const documentedPhotos = Object.values(mediaContext.window.MENIGAR_FAMILY_MEDIA).map(item => item.src);
for (const [, src] of featuredMarkup.matchAll(/<img src="([^"]+)"/g)) assert.ok(documentedPhotos.includes(src), `Foto sin procedencia documentada en portada: ${src}`);
assert.match(homepage, /Laboratorio · archivo 2017/);

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
